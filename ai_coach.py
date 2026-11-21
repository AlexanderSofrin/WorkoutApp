import os
import json
import re
import ssl
import uuid
import time
import random
import urllib.request
import urllib.parse
from datetime import datetime
from sqlalchemy.orm import Session
from db_models import User, Workout, Exercise
from coach_parser import parse_workout_command, parse_weight_update

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
    """Убирает звёздочки ** и служебные JSON-блоки из текста ответа для чистого отображения."""
    text = re.sub(r"\[PLAN_JSON\].*?\[/PLAN_JSON\]", "", text, flags=re.DOTALL)
    text = text.replace("**", "").replace("__", "")
    return text.strip()


def _extract_target_date(text: str) -> str | None:
    """Извлекает дату вида '26 число', '26.11', '26 ноября', 'сегодня' и возвращает YYYY-MM-DD."""
    now = datetime.now()
    low = text.lower()
    if "сегодня" in low:
        return now.strftime("%Y-%m-%d")

    months = {
        "январ": 1, "феврал": 2, "март": 3, "апрел": 4, "ма": 5, "июн": 6,
        "июл": 7, "август": 8, "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12
    }
    m_word = re.search(r"\b(\d{1,2})\s+(январ|феврал|март|апрел|ма|июн|июл|август|сентябр|октябр|ноябр|декабр)[а-яё]*", low)
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

    m_day = re.search(r"\bна\s+(\d{1,2})(?:\s*-?\s*(?:е|ое|го))?\s*(?:числ[оае]?)?\b", low)
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
    """Извлекает тренировочный план из ответа LLM (JSON, таблица или список) и кладёт в буфер."""
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

    if not items:
        for line in llm_text.splitlines():
            line_s = line.strip()
            if not line_s.startswith("|") or line_s.startswith("|---") or "упражнен" in line_s.lower():
                continue
            cols = [c.strip(" *") for c in line_s.strip("|").split("|")]
            if len(cols) >= 3 and cols[0]:
                ex_name = _match_catalog_exercise(cols[0], db)
                nums_sets = re.findall(r"\d+", cols[1])
                nums_reps = re.findall(r"\d+", cols[2])
                nums_w = re.findall(r"\d+(?:[.,]\d+)?", cols[3]) if len(cols) > 3 else []
                items.append({
                    "exercise_name": ex_name,
                    "sets": int(nums_sets[0]) if nums_sets else 3,
                    "reps": int(nums_reps[-1]) if nums_reps else 12,
                    "weight": float(nums_w[0].replace(",", ".")) if nums_w else 0.0,
                    "done": False
                })

    if not items:
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


def _fast_parse_live_copilot(user_id: int, message: str, db: Session, first_name: str) -> dict | None:
    """
    МГНОВЕННЫЙ FAST-PATH (~20 мс, без обращения к LLM):
    1) Старт/смена упражнения: 'начинаю тренировку, сейчас буду делать молотки 10 кг'
    2) Серия подходов на лету: 'первый подход 10 кг на 15, второй 16, третий 18, четвёртый 24 на пампе'
    3) Пошаговое добавление в черновик: 'добавь молотки 4 по 15, вес 15.5 кг'
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

    # 2. Серия подходов в реальном времени ('первый 15, второй 16, третий 18, четвёртый 24, вес 10 кг')
    ordinals = re.findall(
        r"(?:перв\w+|втор\w+|трет\w+|четв[её]рт\w+|пят\w+|\d+-?[йм])\s*(?:подход)?\s*(?:в|на|по)?\s*(\d+)\s*(?:раз|повтор\w*|на\s*памп\w*)?",
        low
    )
    if len(ordinals) >= 2:
        active = _ACTIVE_EXERCISES.get(user_id, {})
        ex_name = active.get("name", "")
        if not ex_name:
            # Пробуем вытащить упражнение из фразы, если не объявляли заранее
            cleaned_phrase = re.sub(r"(?:перв\w+|втор\w+|трет\w+|четв[её]рт\w+|пят\w+|\d+-?[йм]).*", "", low).strip(" .,-")
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

    # 3. Пошаговое добавление упражнения в черновик плана ('добавь молотки 4 по 15, вес 15.5 кг')
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
    """Быстрый вызов GigaChat API с ограниченным объёмом генерации (max_tokens=340)."""
    token = _get_gigachat_token()
    if not token:
        return None

    model_name = os.getenv("GIGACHAT_MODEL", "GigaChat").strip()
    chat_url = "".join(["https://", "gigachat.devices.", "sberbank.ru", "/api/v1/chat/completions"])

    body = json.dumps({
        "model": model_name,
        "messages": messages,
        "temperature": 0.45,
        "max_tokens": 340
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
        with urllib.request.urlopen(req, timeout=14, context=_SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices") or []
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        print("GigaChat Chat error:", e)
        return None
    return None

def generate_coach_reply(message: str, user: User, db: Session, detect_muscle_fn=None) -> dict:

    clean_msg = message.strip()
    low_msg = clean_msg.lower()
    first_name = (user.full_name or "Атлет").split()[0]

    # 1. Подтверждение переноса накопленного черновика / предложенного плана в "План тренировки"
    pending = _PENDING_PLANS.get(user.id)
    cleaned_confirm = re.sub(r"[^\w\sа-яё]", "", low_msg).strip()
    is_confirm = (
        cleaned_confirm in CONFIRM_WORDS
        or any(phrase in low_msg for phrase in ("в план", "добавь план", "перенеси план", "сохрани план"))
    )
    if pending and pending.get("items") and is_confirm:
        items = pending["items"]
        target_date = _extract_target_date(clean_msg) or pending.get("target_date")
        names_preview = ", ".join(i["exercise_name"] for i in items)
        compress_session_memory(user.id, f"Утверждён план: {names_preview}")
        reply = (
            f"Принято, {first_name}! Перенёс всё в «План тренировки» ({names_preview}). "
            f"Проверь позиции ниже и жми «Записать всю тренировку в БД», когда будешь готов."
        )
        return {
            "reply": reply,
            "mode": "plan_approved",
            "suggested_plan": items,
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
        append_session_memory(user.id, "user", clean_msg)
        append_session_memory(user.id, "assistant", reply)
        return {
            "reply": reply,
            "mode": "live_set",
            "workout_entry": parsed,
            "updated_weight_kg": None,
            "suggested_plan": None,
            "target_date": None
        }

    # 5. Ускоренный диалог с GigaChat (кэшированный OAuth + сжатый контекст + парсинг предложенного плана)
    recent_workouts = (
        db.query(Workout)
        .filter(Workout.user_id == user.id)
        .order_by(Workout.created_at.desc())
        .limit(5)
        .all()
    )
    recent_summary = ", ".join(
        f"{w.exercise_name} {w.sets}x{w.reps} ({w.weight} кг)" for w in recent_workouts
    ) or "пока без записей"

    active_ex = _ACTIVE_EXERCISES.get(user.id)
    active_note = (
        f"Текущее упражнение в работе: {active_ex['name']} (вес {active_ex.get('weight', 0)} кг)."
        if active_ex else "Активное упражнение сейчас не выбрано."
    )
    compressed_note = _COMPRESSED_CONTEXT.get(user.id, "")

    system_prompt = (
        f"Ты — персональный ИИ-тренер и нутрициолог в Workout Vault для атлета {first_name} "
        f"(вес {user.weight_kg} кг, цель {user.target_weight_kg} кг). "
        f"Общайся живо, по-дружески на «ты», кратко и по делу (без воды и без символов ** или #). "
        f"Недавние записи: {recent_summary}. {active_note} {compressed_note}\n"
        f"Если атлет просит составить тренировку или программу, выведи её строго нумерованным списком:\n"
        f"1. Название упражнения — 3 подхода × 12 повторений | Вес: 15 кг\n"
        f"И в конце спроси: «Добавить эту тренировку в план?»"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for item in _CHAT_WINDOWS.get(user.id, []):
        messages.append(item)
    messages.append({"role": "user", "content": clean_msg})

    llm_raw = _call_gigachat_llm(messages)
    if llm_raw:
        reply = _extract_and_store_plan(user.id, llm_raw, db, _extract_target_date(clean_msg))
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
        f"или собирать тренировку по упражнениям («Добавь подъём на бицепс 4 по 16, 13 кг»)."
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




