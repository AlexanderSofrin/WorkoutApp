from typing import Optional
import os
import json
import re
import ssl
import uuid
import time
import random
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import func
from sqlalchemy.orm import Session
from db_models import User, Workout, Exercise, DailyNutritionLog

from coach_parser import parse_workout_command, parse_weight_update, parse_batch_workout_log


# ==============================================================================================
# ТРЁХУРОВНЕВАЯ БЫСТРАЯ ПАМЯТЬ + ЖИВАЯ СЕССИЯ ТРЕНИРОВКИ (Live Copilot + Черновик плана)
# ==============================================================================================
_CHAT_WINDOWS: dict[int, list[dict]] = {}
_COMPRESSED_CONTEXT: dict[int, str] = {}
_PENDING_PLANS: dict[int, dict] = {}
_ACTIVE_EXERCISES: dict[int, dict] = {}  # {user_id: {"name": str, "weight": float}}
MAX_WINDOW_MESSAGES = 8

_GIGACHAT_TOKEN_CACHE: dict[str, object] = {"token": "", "expires_at": 0.0}
_SSL_CTX = ssl._create_unverified_context()

CONFIRM_WORDS = {
    "да", "давай", "добавляй", "добавь", "согласен", "погнали",
    "ок", "окей", "хорошо", "утверждаю", "записывай в план", "в план",
    "запиши", "записывай", "записать", "переноси", "перенеси", "готово"
}

FAST_SET_PRAISES = [
    "Чётко, {name}! Записал в план: {summary}. Отдышись спокойно и жми таймер, когда будешь готов.",
    "Отличный темп, {name}! Зафиксировал: {summary}. Контролируй негативную фазу и береги связки.",
    "Мощно зашло, {name}! Внёс в план: {summary}. Пей воду и восстанавливай дыхание перед следующим подходом.",
    "Принято в работу, {name}! Записал: {summary}. Двигаемся ровно и без лишней суеты."
]


def _now_msk() -> datetime:
    try:
        return datetime.now(ZoneInfo("Europe/Moscow"))
    except Exception:
        return datetime.now()


def append_session_memory(user_id: int, role: str, content: str) -> None:
    """Уровень 1: Скользящее окно последних 8 реплик для живого непрерывного диалога."""
    history = _CHAT_WINDOWS.setdefault(user_id, [])
    history.append({"role": role, "content": content})
    if len(history) > MAX_WINDOW_MESSAGES:
        _CHAT_WINDOWS[user_id] = history[-MAX_WINDOW_MESSAGES:]


def compress_session_memory(user_id: int, summary_note: str) -> None:
    """Уровень 3: Сжатие истории диалога после утверждения плана или записи тренировки в БД."""
    _COMPRESSED_CONTEXT[user_id] = summary_note
    _CHAT_WINDOWS[user_id] = []
    _PENDING_PLANS.pop(user_id, None)


def _clean_markdown(text: str) -> str:
    """Убирает служебные JSON-блоки, сохраняя жирные акценты **...** и заголовки для красивого рендера."""
    text = re.sub(r"\[PLAN_JSON\].*?\[/PLAN_JSON\]", "", text, flags=re.DOTALL)
    text = text.replace("__", "")
    return text.strip()




def _extract_target_date(text: str) -> str | None:
    """Извлекает дату вида 'сегодня', 'вчера', '17 число', '1.11', '1 ноября' и возвращает YYYY-MM-DD."""
    now = _now_msk()
    low = text.lower()
    if "сегодня" in low:
        return now.strftime("%Y-%m-%d")
    if "позавчера" in low:
        return (now - timedelta(days=2)).strftime("%Y-%m-%d")
    if "вчера" in low:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")

    months = {
        "январ": 1, "феврал": 2, "март": 3, "апрел": 4, "ма": 5, "июн": 6,
        "июл": 7, "август": 8, "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12
    }
    m_word = re.search(
        r"\b(\d{1,2})\s+(январ|феврал|март|апрел|ма|июн|июл|август|сентябр|октябр|ноябр|декабр)[а-яё]*",
        low
    )
    if m_word:
        day = int(m_word.group(1))
        month = months[m_word.group(2)]
        year = now.year + (1 if month < now.month - 6 else 0)
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            pass

    m_dot = re.search(r"\b(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?\b", text)
    if m_dot:
        day, month = int(m_dot.group(1)), int(m_dot.group(2))
        year = int(m_dot.group(3)) if m_dot.group(3) else now.year
        if year < 100:
            year += 2000
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            pass

    m_day = re.search(
        r"\b(?:на|за|от)\s+(\d{1,2})(?:\s*-?\s*(?:е|ое|го|му))?\s*(?:числ[оаеу]?)?\b",
        low
    )
    if m_day:
        day = int(m_day.group(1))
        try:
            return datetime(now.year, now.month, day).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None
def _match_catalog_exercise(raw_name: str, db: Session) -> str:
    """Подбирает точное название из каталога упражнений, чтобы не плодить дубли в БД."""
    if not raw_name:
        return ""
    all_ex = db.query(Exercise.name).all()
    if not all_ex:
        return raw_name
    raw_low = raw_name.lower().strip()
    for (cat_name,) in all_ex:
        if raw_low in cat_name.lower() or cat_name.lower() in raw_low:
            return cat_name
    words = [w for w in re.findall(r"[а-яёa-z]{4,}", raw_low)]
    for (cat_name,) in all_ex:
        cat_low = cat_name.lower()
        if words and all(w[:4] in cat_low for w in words[:2]):
            return cat_name
    return raw_name


def _extract_and_store_plan(user_id: int, llm_text: str, db: Session, target_date: str | None = None) -> str:
    """Извлекает тренировочный план из ответа LLM (JSON или список) и кладёт в буфер."""
    items = []
    m = re.search(r"\[PLAN_JSON\](.*?)\[/PLAN_JSON\]", llm_text, flags=re.DOTALL)
    if m:
        try:
            raw_list = json.loads(m.group(1).strip())
            if isinstance(raw_list, list):
                for item in raw_list:
                    ex_name = _match_catalog_exercise(str(item.get("exercise_name", "")).strip(), db)
                    if ex_name:
                        items.append({
                            "exercise_name": ex_name,
                            "sets": int(item.get("sets") or 3),
                            "reps": int(item.get("reps") or 12),
                            "weight": float(item.get("weight") or 0),
                            "done": False
                        })
        except Exception:
            items = []

    if not items and "добавить эту тренировку в план" in llm_text.lower():
        for line in llm_text.splitlines():
            m_num = re.match(r"^\s*\d+[\.\)]\s+(.+)$", line.strip())
            if not m_num:
                continue
            raw_title = re.sub(r"\*+", "", m_num.group(1)).strip()
            raw_title = re.split(r"\s*[—–-]\s*|\s*\(", raw_title)[0].strip()
            if len(raw_title) < 4:
                continue
            ex_name = _match_catalog_exercise(raw_title, db)
            m_sr = re.search(r"(\d+)\s*(?:подход[а-я]*|x|х|\*)\s*(?:по\s*)?(\d+)", line.lower())
            m_w = re.search(r"(\d+(?:[.,]\d+)?)\s*кг", line.lower())
            items.append({
                "exercise_name": ex_name,
                "sets": int(m_sr.group(1)) if m_sr else 3,
                "reps": int(m_sr.group(2)) if m_sr else 12,
                "weight": float(m_w.group(1).replace(",", ".")) if m_w else 0.0,
                "done": False
            })

    if items:
        existing = _PENDING_PLANS.get(user_id, {})
        prev_date = existing.get("target_date")
        _PENDING_PLANS[user_id] = {
            "items": items,
            "target_date": target_date or prev_date
        }
    return _clean_markdown(llm_text)


def _fast_parse_live_copilot(user_id: int, message: str, db: Session, first_name: str) -> Optional[dict]:
    """
    МГНОВЕННЫЙ FAST-PATH (~20 мс, без обращения к LLM):
    1) Старт/смена упражнения
    2) Серия подходов на лету
    3) Пошаговое добавление в черновик плана
    """
    low = message.lower().strip()
    target_date = _extract_target_date(message)

    # 1. Старт или переключение текущего упражнения во время тренировки
    m_start = re.search(
        r"(?:начинаю\s+тренировк\w*|сейчас\s+(?:буду\s+)?дела\w*|дальше\s+(?:будем\s+)?дела\w*|следующ\w*\s+упражнен\w*)\s*[:,-]?\s*(.+)",
        low
    )
    if m_start and not re.search(r"(?:первый|второй|третий|четвертый|четвёртый|1-й|2-й|3-й|4-й)\s+(?:подход)?", low):
        tail = m_start.group(1).strip()
        w_m = re.search(r"(\d+(?:[.,]\d+)?)\s*кг", tail)
        weight = float(w_m.group(1).replace(",", ".")) if w_m else 0.0
        clean_ex = re.sub(r"\d+(?:[.,]\d+)?\s*кг.*", "", tail).strip(" .,-")
        if len(clean_ex) >= 3:
            matched_name = _match_catalog_exercise(clean_ex, db)
            _ACTIVE_EXERCISES[user_id] = {"name": matched_name, "weight": weight}
            w_note = f" (рабочий вес {weight} кг)" if weight > 0 else ""
            reply = f"Погнали, {first_name}! Зафиксировал текущее упражнение: {matched_name}{w_note}. Диктуй подходы по ходу работы!"
            append_session_memory(user_id, "user", message)
            append_session_memory(user_id, "assistant", reply)
            return {
                "reply": reply,
                "mode": "chat",
                "used_llm": False,
                "workout_entry": None,
                "suggested_plan": None,
                "target_date": target_date
            }

    # 2. Серия подходов в реальном времени
    ordinals = re.findall(
        r"(?:перв\w+|втор\w+|трет\w+|четв[её]рт\w+|пят\w+|\d+-?[йм])\s*(?:подход)?\s*(?:в|на|по)?\s*(\d+)\s*(?:раз|повтор\w*|на\s*памп\w*)?",
        low
    )
    if len(ordinals) >= 2:
        active = _ACTIVE_EXERCISES.get(user_id, {})
        ex_name = active.get("name", "")
        if not ex_name:
            cleaned_phrase = re.sub(
                r"(?:перв\w+|втор\w+|трет\w+|четв[её]рт\w+|пят\w+|\d+-?[йм]).*", "", low
            ).strip(" .,-")
            if len(cleaned_phrase) >= 3:
                ex_name = _match_catalog_exercise(cleaned_phrase, db)
        if not ex_name:
            ex_name = "Упражнение текущей тренировки"

        w_m = re.search(r"(\d+(?:[.,]\d+)?)\s*кг", low)
        weight = float(w_m.group(1).replace(",", ".")) if w_m else float(active.get("weight", 0.0))
        if weight > 0:
            _ACTIVE_EXERCISES[user_id] = {"name": ex_name, "weight": weight}

        reps_list = [int(r) for r in ordinals]
        entries = [{"sets": 1, "reps": r, "weight": weight} for r in reps_list]
        total_reps = sum(reps_list)
        tonnage = round(total_reps * weight, 1)
        reps_str = ", ".join(str(r) for r in reps_list)
        ton_note = f" (тоннаж {tonnage} кг)" if tonnage > 0 else ""

        reply = (
            f"Огонь, {first_name}! Закрыли «{ex_name}»: {len(reps_list)} подхода "
            f"({reps_str} повторений × {weight} кг){ton_note}. Перенёс в «План тренировки». Что ставим дальше?"
        )
        append_session_memory(user_id, "user", message)
        append_session_memory(user_id, "assistant", reply)
        return {
            "reply": reply,
            "mode": "live_set",
            "used_llm": False,
            "workout_entry": {
                "exercise_name": ex_name,
                "entries": entries
            },
            "suggested_plan": None,
            "target_date": target_date
        }

    # 3. Пошаговое добавление упражнения в черновик плана
    m_add = re.match(r"^(?:добавь|ещ[её]\s+добавь|поставь|закинь|плюс)\s+(.+)$", low)
    if m_add and not any(w in low for w in ("в план", "тренировку в бд", "в базу")):
        tail = m_add.group(1).strip()
        m_sr = re.search(r"(\d+)\s*(?:подход[а-я]*|x|х|\*)\s*(?:по\s*)?(\d+)", tail)
        m_w = re.search(r"(\d+(?:[.,]\d+)?)\s*кг", tail)
        sets = int(m_sr.group(1)) if m_sr else 3
        reps = int(m_sr.group(2)) if m_sr else 12
        weight = float(m_w.group(1).replace(",", ".")) if m_w else 0.0

        ex_raw = re.split(r"\d+\s*(?:подход|x|х|\*)|\d+(?:[.,]\d+)?\s*кг", tail)[0].strip(" .,-")
        if len(ex_raw) >= 3:
            ex_name = _match_catalog_exercise(ex_raw, db)
            buf = _PENDING_PLANS.setdefault(user_id, {"items": [], "target_date": target_date})
            if target_date:
                buf["target_date"] = target_date
            buf["items"].append({
                "exercise_name": ex_name,
                "sets": sets,
                "reps": reps,
                "weight": weight,
                "done": False
            })
            count = len(buf["items"])
            w_txt = f", {weight} кг" if weight > 0 else ""
            reply = (
                f"Добавил в черновик (#{count}): {ex_name} — {sets}×{reps}{w_txt}. "
                f"Диктуй следующее упражнение или скажи «Всё, добавь в план»."
            )
            append_session_memory(user_id, "user", message)
            append_session_memory(user_id, "assistant", reply)
            return {
                "reply": reply,
                "mode": "chat",
                "used_llm": False,
                "workout_entry": None,
                "suggested_plan": None,
                "target_date": buf.get("target_date")
            }

    return None
def _get_gigachat_token() -> str | None:
    """Получает и кэширует OAuth-токен GigaChat на 29 минут."""
    auth_key = os.getenv("GIGACHAT_AUTH_KEY", "").strip()
    if not auth_key:
        return None
    now = time.time()
    if _GIGACHAT_TOKEN_CACHE["token"] and now < float(_GIGACHAT_TOKEN_CACHE["expires_at"]):
        return str(_GIGACHAT_TOKEN_CACHE["token"])

    scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS").strip()
    oauth_url = "".join(["https://", "ngw.devices.", "sberbank.ru:9443", "/api/v2/oauth"])

    data = urllib.parse.urlencode({"scope": scope}).encode("utf-8")
    req = urllib.request.Request(
        oauth_url,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "Authorization": f"Basic {auth_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8, context=_SSL_CTX) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            tok = payload.get("access_token", "")
            if tok:
                _GIGACHAT_TOKEN_CACHE["token"] = tok
                _GIGACHAT_TOKEN_CACHE["expires_at"] = now + 1700
                return tok
    except Exception as e:
        print("GigaChat OAuth error:", e)
        return None
    return None


def _call_gigachat_llm(messages: list[dict]) -> str | None:
    """Быстрый вызов GigaChat API с оптимальным балансом глубины и скорости (max_tokens=420)."""
    token = _get_gigachat_token()
    if not token:
        return None

    model_name = os.getenv("GIGACHAT_MODEL", "GigaChat").strip()
    chat_url = "".join(["https://", "gigachat.devices.", "sberbank.ru", "/api/v1/chat/completions"])

    body = json.dumps({
        "model": model_name,
        "messages": messages,
        "temperature": 0.35,
        "max_tokens": 700
    }).encode("utf-8")

    req = urllib.request.Request(
        chat_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=25, context=_SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices") or []
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        print("GigaChat Chat error:", e)
        return None
    return None


def _build_user_context(user: User, db: Session, target_date: str | None = None) -> str:
    """
    Собирает живое досье атлета из PostgreSQL (users + workouts + daily_nutrition_logs)
    + точный срез за запрошенную дату target_date из архива, если пользователь её назвал.
    """
    now = _now_msk()
    weekdays_ru = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    time_line = (
        f"Текущее время (МСК): {now.strftime('%d.%m.%Y %H:%M')} ({weekdays_ru[now.weekday()]})."
    )

    goal_map = {
        "cut": "сушка и рельеф",
        "recomp": "рекомпозиция (рост мышц при контроле жира)",
        "bulk": "качественный набор мышечной массы"
    }
    goal_text = goal_map.get(user.goal or "recomp", user.goal or "рекомпозиция")

    protections = []
    if getattr(user, "protect_lower_back", True):
        protections.append("поясницу")
    if getattr(user, "protect_knees", True):
        protections.append("колени")
    if getattr(user, "protect_elbows", True):
        protections.append("связки локтей")
    if user.injury_notes:
        protections.append(f"заметки: {user.injury_notes}")
    protect_str = ", ".join(protections) if protections else "стандартный контроль техники"

    profile_line = (
        f"Профиль: вес {user.weight_kg or '?'} кг (цель {user.target_weight_kg or '?'} кг), "
        f"рост {user.height_cm or '?'} см, цель — {goal_text}, график работы {user.work_schedule or '2/2'}, "
        f"стаж {user.experience_years or 1.0} г. Беречь: {protect_str}."
    )

    specific_date_line = ""
    if target_date:
        try:
            dt_start = datetime.strptime(target_date, "%Y-%m-%d")
            dt_end = dt_start + timedelta(days=1)
            date_rows = (
                db.query(Workout)
                .filter(
                    Workout.user_id == user.id,
                    Workout.created_at >= dt_start,
                    Workout.created_at < dt_end
                )
                .order_by(Workout.id.asc())
                .all()
            )
            if date_rows:
                total_tonnage = 0.0
                ex_list = []
                for w in date_rows:
                    w_val = float(w.weight or 0.0)
                    total_tonnage += w.sets * w.reps * w_val
                    w_txt = f"{w_val} кг" if w_val > 0 else "свой вес"
                    ex_list.append(f"{w.exercise_name}: {w.sets}×{w.reps} ({w_txt})")
                specific_date_line = (
                    f"\nАРХИВ ЗА ЗАПРОШЕННУЮ ДАТУ ({dt_start.strftime('%d.%m.%Y')}): "
                    + "; ".join(ex_list)
                    + f" | Общий тоннаж: {round(total_tonnage)} кг."
                )
            else:
                specific_date_line = (
                    f"\nАРХИВ ЗА ЗАПРОШЕННУЮ ДАТУ ({dt_start.strftime('%d.%m.%Y')}): "
                    f"в базе за этот день тренировок не найдено."
                )
        except Exception:
            pass

    recent_rows = (
        db.query(Workout)
        .filter(Workout.user_id == user.id)
        .order_by(Workout.created_at.desc())
        .limit(20)
        .all()
    )
    if recent_rows:
        last_dt = recent_rows[0].created_at
        if last_dt:
            now_naive = now.replace(tzinfo=None)
            hours_since = max(0, int((now_naive - last_dt).total_seconds() // 3600))
            days_since = hours_since // 24
            recovery_note = f" (прошло ~{hours_since} ч / {days_since} дн. с крайней сессии)"
        else:
            recovery_note = ""

        by_day: dict[str, dict[str, list[str]]] = {}
        for w in recent_rows:
            day_key = w.created_at.strftime("%d.%m.%Y") if w.created_at else "без даты"
            ex_map = by_day.setdefault(day_key, {})
            w_txt = f"{w.weight}кг" if w.weight else "св.вес"
            ex_map.setdefault(w.exercise_name, []).append(f"{w.sets}×{w.reps}({w_txt})")

        day_summaries = []
        for day_key, ex_map in list(by_day.items())[:4]:
            ex_parts = [f"{ex}: {', '.join(sets_list)}" for ex, sets_list in ex_map.items()]
            day_summaries.append(f"[{day_key}] " + "; ".join(ex_parts))
        workouts_line = f"Последние тренировки{recovery_note}: " + " | ".join(day_summaries)
    else:
        workouts_line = "Последние тренировки: записей в базе пока нет."

    nutri_rows = (
        db.query(DailyNutritionLog)
        .filter(DailyNutritionLog.user_id == user.id)
        .order_by(DailyNutritionLog.log_date.desc())
        .limit(3)
        .all()
    )
    if nutri_rows:
        n_parts = [
            f"{n.log_date}: {n.consumed_kcal}/{n.target_kcal} ккал (Б:{n.protein_g} Ж:{n.fats_g} У:{n.carbs_g})"
            for n in nutri_rows
        ]
        nutrition_line = "Питание (свежие дни): " + "; ".join(n_parts)
    else:
        nutrition_line = "Питание: логов КБЖУ за последние дни пока нет."

    return f"{time_line}\n{profile_line}{specific_date_line}\n{workouts_line}\n{nutrition_line}"
def _extract_all_dates(text: str) -> list:
    now = _now_msk()
    low = text.lower()
    found = []
    if "сегодня" in low:
        found.append(now.strftime("%Y-%m-%d"))
    if "завтра" in low and "послезавтра" not in low:
        found.append((now + timedelta(days=1)).strftime("%Y-%m-%d"))
    if "послезавтра" in low:
        found.append((now + timedelta(days=2)).strftime("%Y-%m-%d"))
    months = {
        "январ": 1, "феврал": 2, "март": 3, "апрел": 4, "ма": 5, "июн": 6,
        "июл": 7, "август": 8, "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12
    }
    for m in re.finditer(r"\b(\d{1,2})\s+(январ|феврал|март|апрел|ма|июн|июл|август|сентябр|октябр|ноябр|декабр)[а-яё]*", low):
        day, month = int(m.group(1)), months[m.group(2)]
        year = now.year + (1 if month < now.month - 6 else 0)
        try:
            d_s = datetime(year, month, day).strftime("%Y-%m-%d")
            if d_s not in found:
                found.append(d_s)
        except ValueError:
            pass
    for m in re.finditer(r"\b(?:с|со|на|за|от)\s+(\d{1,2})(?:\s*-?\s*(?:е|ое|го|му))?\s*(?:числ[оаеу]?)?\b", low):
        day = int(m.group(1))
        try:
            d_s = datetime(now.year, now.month, day).strftime("%Y-%m-%d")
            if d_s not in found:
                found.append(d_s)
        except ValueError:
            pass
    return found


def _handle_schedule_dialog(user_id: int, message: str, scheduled_plans: Optional[dict], first_name: str) -> Optional[dict]:
    sched = scheduled_plans or {}
    low = message.lower().strip()
    dates = _extract_all_dates(message)

    if any(w in low for w in ("перенес", "сдвин", "перестав")) and dates:
        src_date = None
        dst_date = None
        if len(dates) >= 2:
            src_date, dst_date = dates, dates
        elif len(dates) == 1:
            dst_date = dates
            for k in sorted(sched.keys()):
                if sched.get(k) and k != dst_date:
                    src_date = k
                    break
        if src_date and dst_date and sched.get(src_date):
            items = sched[src_date]
            s_fmt = datetime.strptime(src_date, "%Y-%m-%d").strftime("%d.%m.%Y")
            d_fmt = datetime.strptime(dst_date, "%Y-%m-%d").strftime("%d.%m.%Y")
            names = ", ".join(it.get("name") or it.get("exercise_name") or "" for it in items)
            reply = f"Перенёс тренировку ({names}) с {s_fmt} на {d_fmt}. В календаре {d_fmt} теперь отмечено фиолетовым!"
            append_session_memory(user_id, "user", message)
            append_session_memory(user_id, "assistant", reply)
            return {
                "reply": reply,
                "mode": "plan_moved",
                "from_date": src_date,
                "target_date": dst_date,
                "suggested_plan": items,
                "workout_entry": None,
                "updated_weight_kg": None
            }

    if any(w in low for w in ("отмен", "удал", "убер", "сним")) and any(w in low for w in ("тренировк", "план", "запис", "числ", "завтра", "сегодня")):
        target_d = dates if dates else next((k for k in sorted(sched.keys()) if sched.get(k)), None)
        if target_d and sched.get(target_d):
            d_fmt = datetime.strptime(target_d, "%Y-%m-%d").strftime("%d.%m.%Y")
            reply = f"Снял запланированную тренировку на {d_fmt} и очистил фиолетовую отметку в календаре. Если решишь поставить её на другой день — просто скажи!"
            append_session_memory(user_id, "user", message)
            append_session_memory(user_id, "assistant", reply)
            return {
                "reply": reply,
                "mode": "plan_cancelled",
                "target_date": target_d,
                "suggested_plan": None,
                "workout_entry": None,
                "updated_weight_kg": None
            }

    is_asking_plan = any(p in low for p in ("что у нас", "что запланировано", "что намечено", "какая тренировка на", "какой план на", "покажи план на"))
    if is_asking_plan and dates:
        q_date = dates
        d_fmt = datetime.strptime(q_date, "%Y-%m-%d").strftime("%d.%m.%Y")
        items = sched.get(q_date) or []
        if items:
            lines = [
                f"{idx + 1}. {it.get('name') or it.get('exercise_name')} — {it.get('sets', 3)}×{it.get('reps', 12)} ({it.get('weight', 0)} кг)"
                for idx, it in enumerate(items)
            ]
            reply = (
                f"На {d_fmt} у нас намечена тренировка:\n" + "\n".join(lines) +
                f"\nОставляем в силе, отменяем или переносим на другую дату?"
            )
        else:
            reply = f"На {d_fmt} в календаре пока пусто, {first_name}. Составить и поставить тренировку на этот день?"
        append_session_memory(user_id, "user", message)
        append_session_memory(user_id, "assistant", reply)
        return {
            "reply": reply,
            "mode": "chat",
            "target_date": q_date,
            "suggested_plan": None,
            "workout_entry": None,
            "updated_weight_kg": None
        }

    return None


def generate_coach_reply(message: str, user: User, db: Session, detect_muscle_fn=None, current_plan: Optional[list] = None, scheduled_plans: Optional[dict] = None) -> dict:

    clean_msg = message.strip()
    low_msg = clean_msg.lower()
    first_name = (user.full_name or "Атлет").split()[0]
    target_date = _extract_target_date(clean_msg)

    # 0. Живое управление расписанием в календаре (просмотр, отмена, перенос между датами)
    sched_res = _handle_schedule_dialog(user.id, clean_msg, scheduled_plans, first_name)
    if sched_res:
        return sched_res

    # 1. Прямая запись выполненной тренировки в блокнот (PostgreSQL) одной фразой
    is_log_completed = any(
        phrase in low_msg for phrase in (
            "тренировка выполнена", "записывай в блокнот", "запиши в блокнот",
            "в дневник", "в журнал", "в историю", "запиши всю тренировку", "закрыли тренировку"
        )
    )
    pending = _PENDING_PLANS.get(user.id)
    active_items = (pending.get("items") if pending and pending.get("items") else None) or (
        current_plan if current_plan else None)
    if active_items and is_log_completed:
        norm_items = []
        for it in active_items:
            ex_n = it.get("exercise_name") or it.get("name") or ""
            if ex_n:
                norm_items.append({
                    "exercise_name": ex_n,
                    "sets": int(it.get("sets") or 3),
                    "reps": int(it.get("reps") or 12),
                    "weight": float(it.get("weight") or 0),
                    "done": True
                })
        final_date = target_date or (pending.get("target_date") if pending else None)
        names_preview = ", ".join(i["exercise_name"] for i in norm_items)
        compress_session_memory(user.id, f"Выполнена и записана в блокнот: {names_preview}")
        reply = (
            f"Мощно отработал, {first_name}! Записал всю выполненную тренировку ({names_preview}) "
            f"прямо в твой блокнот и обновил средний расход калорий на главной."
        )
        return {
            "reply": reply,
            "mode": "workout_logged",
            "suggested_plan": norm_items,
            "target_date": final_date,
            "workout_entry": None,
            "updated_weight_kg": None
        }
    # 1.5. ПАКЕТНАЯ ЗАПИСЬ ВСЕЙ ТРЕНИРОВКИ ОДНИМ СПИСКОМ (многострочный отчёт)
    batch_items = parse_batch_workout_log(clean_msg)
    if batch_items:
        norm_batch = []
        total_sets = 0
        total_tonnage = 0.0
        summary_lines = []
        for it in batch_items:
            matched_ex = _match_catalog_exercise(it["exercise_name"], db)
            s_cnt = int(it["sets"])
            r_cnt = int(it["reps"])
            w_val = float(it["weight"])
            total_sets += s_cnt
            total_tonnage += s_cnt * r_cnt * w_val
            norm_batch.append({
                "exercise_name": matched_ex,
                "sets": s_cnt,
                "reps": r_cnt,
                "weight": w_val,
                "done": True
            })
            w_label = f" ({w_val} кг)" if w_val > 0 else " (свой вес / резинка)"
            summary_lines.append(f"• **{matched_ex}**: {s_cnt}×{r_cnt}{w_label}")

        tonnage_note = f", общий тоннаж — **{round(total_tonnage)} кг**" if total_tonnage > 0 else ""

        coach_comment = ""
        try:
            review_prompt = (
                    f"Ты — персональный ИИ-тренер атлета {first_name} (вес {user.weight_kg or 67} кг, цель: {user.target_weight_kg or 67} кг). "
                    f"Атлет только что выполнил и записал в блокнот реальную тренировку:\n"
                    + "\n".join(summary_lines)
                    + f"\nИтого: {len(norm_batch)} упражнений, {total_sets} подходов{tonnage_note}.\n"
                      f"Напиши короткий, умный тренерский комментарий (3–4 предложения): оцени объём и распределение нагрузки, "
                      f"укажи примерный расход ккал с учётом веса тела и дай 1 конкретный совет по восстановлению и питанию после этой сессии. "
                      f"Не переписывай заново весь список упражнений."
            )
            llm_comment = _call_gigachat_llm([{"role": "system", "content": review_prompt}])
            if llm_comment:
                coach_comment = "\n\n" + _clean_markdown(llm_comment)
        except Exception:
            coach_comment = ""

        reply = (
                f"**Отличная работа, {first_name}! Записал всю тренировку ({len(norm_batch)} поз., {total_sets} подх.{tonnage_note}) в блокнот и календарь.**\n\n"
                + "\n".join(summary_lines)
                + coach_comment
        )
        compress_session_memory(user.id,
                                f"Пакетно записана тренировка: {len(norm_batch)} упражнений, {total_sets} подходов")
        return {
            "reply": reply,
            "mode": "workout_logged",
            "suggested_plan": norm_batch,
            "target_date": target_date,
            "workout_entry": None,
            "updated_weight_kg": None
        }

    # 2. МГНОВЕННЫЙ FAST-PATH (Live Copilot + Черновик плана — отклик ~20 мс без ожидания нейросети)
    fast_res = _fast_parse_live_copilot(user.id, clean_msg, db, first_name)
    if fast_res:
        return {
            "reply": fast_res["reply"],
            "mode": fast_res["mode"],
            "suggested_plan": fast_res.get("suggested_plan"),
            "target_date": fast_res.get("target_date"),
            "workout_entry": fast_res.get("workout_entry"),
            "updated_weight_kg": None
        }

    # 3. Обновление веса тела ("мой вес 67.2")
    new_weight = parse_weight_update(clean_msg)
    if new_weight is not None:
        user.weight_kg = new_weight
        db.commit()
        reply = f"Зафиксировал новый вес: {new_weight} кг. Двигаемся в зелёном коридоре к цели {user.target_weight_kg} кг!"
        append_session_memory(user.id, "user", clean_msg)
        append_session_memory(user.id, "assistant", reply)
        return {
            "reply": reply,
            "mode": "weight_updated",
            "updated_weight_kg": new_weight,
            "workout_entry": None,
            "suggested_plan": None,
            "target_date": None
        }
    # 4. Классический парсер одиночного подхода ("подъём гантелей 13 кг 3 по 16")
    parsed = parse_workout_command(clean_msg)
    if parsed and parsed.get("entries"):
        matched_name = _match_catalog_exercise(parsed["exercise_name"], db)
        parsed["exercise_name"] = matched_name
        _ACTIVE_EXERCISES[user.id] = {
            "name": matched_name,
            "weight": parsed["entries"][0].get("weight", 0)
        }
        parts = [f"{e['sets']}×{e['reps']} ({e['weight']} кг)" for e in parsed["entries"]]
        summary = f"{matched_name}: " + ", ".join(parts)
        reply = random.choice(FAST_SET_PRAISES).format(name=first_name, summary=summary)
        append_session_memory(user_id=user.id, role="user", content=clean_msg)
        append_session_memory(user_id=user.id, role="assistant", content=reply)
        return {
            "reply": reply,
            "mode": "live_set",
            "workout_entry": parsed,
            "updated_weight_kg": None,
            "suggested_plan": None,
            "target_date": None
        }

    # 5. Диалог с GigaChat-Max: живой характер напарника + спортивная физиология + контекст БД
    db_context = _build_user_context(user, db, target_date=target_date)

    active_ex = _ACTIVE_EXERCISES.get(user.id)
    active_note = (
        f"Текущее упражнение в работе: {active_ex['name']} (вес {active_ex.get('weight', 0)} кг)."
        if active_ex else ""
    )
    compressed_note = _COMPRESSED_CONTEXT.get(user.id, "")

    sched_lines = []
    if scheduled_plans:
        for d_k, d_items in sorted(scheduled_plans.items()):
            if d_items:
                d_f = datetime.strptime(d_k, "%Y-%m-%d").strftime("%d.%m.%Y")
                ex_s = ", ".join(it.get("name") or it.get("exercise_name") or "" for it in d_items)
                sched_lines.append(f"{d_f}: {ex_s}")
    sched_note = ("ЗАПЛАНИРОВАННЫЕ ТРЕНИРОВКИ В КАЛЕНДАРЕ: " + " | ".join(sched_lines) + "\n") if sched_lines else ""
    system_prompt = (
        f"Ты — персональный ИИ-тренер, спортивный физиолог и мудрый напарник в Workout Vault. "
        f"Общаешься с атлетом {first_name} открыто, размеренно, уважительно и по-товарищески — как опытный наставник рядом со стойкой.\n\n"
        f"ДАННЫЕ АТЛЕТА ИЗ БАЗЫ:\n{db_context}\n{sched_note}{active_note} {compressed_note}\n\n"
        f"ЖЕЛЕЗНЫЕ ПРАВИЛА ПОВЕДЕНИЯ:\n"
        f"0. НИКОГДА НЕ ВЫДУМЫВАЙ УПРАЖНЕНИЯ, ПОДХОДЫ И ВЕСА: если пользователь ещё не перечислил конкретные упражнения и цифры (например, написал «сейчас дам тренировку, занеси в блокнот»), категорически запрещено придумывать тренировку за него! Ответь коротко в 1–2 предложения: «Готов, {first_name}! Диктуй или вставляй список упражнений с подходами, повторениями и весом — сразу аккуратно запишу в блокнот и разберу.»\n"
        f"1. ЖИРНЫЙ ГЛАВНЫЙ ВЫВОД В ПЕРВОМ АБЗАЦЕ: начинай содержательный ответ с 1–2 ёмких предложений, выделенных двойными звёздочками **...**, где сразу даёшь главную оценку, поддержку или прямой ответ по сути.\n"
        f"2. ФИЗИОЛОГИЯ И ЗАБОТА О СУСТАВАХ: кратко и понятно объясняй «почему так» через биомеханику, восстановление ЦНС, баланс давления, гликоген и защиту ключевых зон (поясница, плечевые суставы, колени, связки локтей).\n"
        f"3. СТРУКТУРИРОВАННЫЕ СПИСКИ И ПОДЗАГОЛОВКИ: для разборов, планов и расчётов используй короткие подзаголовки (с новой строки, выделенные **Жирным:**) и буллиты (• **Ключевой акцент:** пояснение с точными подходами, повторениями, весом и временем отдыха).\n"
        f"4. ДОЗИРОВАННАЯ ГЛУБИНА: на короткую реплику между подходами отвечай живо и компактно (3–5 строк). На разбор тренировки, самочувствия, питания или расхода калорий — давай размеренный, логичный разбор по полочкам. Не навязывай непрошеные программы на неделю, если о них не просили.\n"
        f"5. УЧЁТ КОНТЕКСТА И САМОЧУВСТВИЯ: всегда опирайся на реальный вес атлета, цель, график смен 2/2 и историю тренировок из БД. Если атлет отмечает усталость, недосып или лёгкую простуду — мягко снижай нагрузку на голову, сосуды и суставы, хвали за взвешенные решения.\n"
        f"6. ПОКАЗ ТРЕНИРОВКИ ЗА ДАТУ: если просят показать тренировку за конкретное число, выведи чистый список упражнений с подходами, повторениями, весом и общим тоннажем, а в конце дай короткий общий вывод.\n"
        f"7. ГРАНИЦЫ КОМПЕТЕНЦИИ: ты отвечаешь ТОЛЬКО за спорт, тренировки, технику, питание, КБЖУ, режим дня, восстановление мышц/связок и спортивный настрой. На посторонние темы (юриспруденция, финансы, политика, код) тепло отвечай: «Извини, {first_name}, я твой персональный ИИ-тренер: помогаю с тренировками, прогрессией весов, питанием и восстановлением. В этом вопросе не подскажу, но по залу и режиму — всегда в строю!»\n"
        f"8. СОСТАВЛЕНИЕ И ПЛАНИРОВАНИЕ ТРЕНИРОВКИ (ТОЛЬКО КОГДА ЯВНО ПРОСЯТ СОСТАВИТЬ/ЗАПЛАНИРОВАТЬ): выведи нумерованный список в формате:\n"
        f"1. Название упражнения — 3 подхода × 12 повторений | Вес: 15 кг\n"
        f"И в конце спроси: «Добавить эту тренировку в план?»\n"
        f"9. МЯГКИЙ НАПРАВЛЯЮЩИЙ ФИНАЛ: в конце развёрнутого ответа предложи 1–2 конкретных логичных следующих шага или вопроса по теме текущей сессии."
    )

    messages = [{"role": "system", "content": system_prompt}]
    for item in _CHAT_WINDOWS.get(user.id, []):
        messages.append(item)
    messages.append({"role": "user", "content": clean_msg})

    llm_raw = _call_gigachat_llm(messages)
    if llm_raw:
        reply = _extract_and_store_plan(user.id, llm_raw, db, target_date)
        append_session_memory(user.id, "user", clean_msg)
        append_session_memory(user.id, "assistant", reply)
        return {
            "reply": reply,
            "mode": "chat",
            "workout_entry": None,
            "updated_weight_kg": None,
            "suggested_plan": None,
            "target_date": None
        }

    # 6. Фоллбэк, если GigaChat временно недоступен
    fallback_reply = (
        f"{first_name}, я на связи! Можешь сразу диктовать подход (например: «Молотки 12.5 кг 3 по 15») "
        f"или вставить список всей тренировки для записи в блокнот."
    )
    append_session_memory(user.id, "user", clean_msg)
    append_session_memory(user.id, "assistant", fallback_reply)
    return {
        "reply": fallback_reply,
        "mode": "chat",
        "workout_entry": None,
        "updated_weight_kg": None,
        "suggested_plan": None,
        "target_date": None
    }


