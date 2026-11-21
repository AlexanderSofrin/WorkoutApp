import os
import json
import re
import ssl
import uuid
import time
import urllib.request
import urllib.parse
from datetime import datetime
from sqlalchemy.orm import Session
from db_models import User, Workout, Exercise
from coach_parser import parse_workout_command, parse_weight_update

# ==============================================================================================
# ТРЁХУРОВНЕВАЯ БЫСТРАЯ ПАМЯТЬ ИИ-ТРЕНЕРА (Sliding Window + Срез БД + Сжатие + Черновик плана)
# ==============================================================================================
_CHAT_WINDOWS: dict[int, list[dict]] = {}
_COMPRESSED_CONTEXT: dict[int, str] = {}
_PENDING_PLANS: dict[int, list[dict]] = {}
MAX_WINDOW_MESSAGES = 10

_GIGACHAT_TOKEN_CACHE: dict[str, object] = {"token": "", "expires_at": 0.0}

CONFIRM_WORDS = {
    "да", "давай", "добавляй", "добавь", "согласен", "погнали",
    "ок", "окей", "хорошо", "утверждаю", "записывай в план", "в план",
    "запиши", "записывай", "записать", "переноси", "перенеси"
}



def append_session_memory(user_id: int, role: str, content: str) -> None:
    """Уровень 1: Скользящее окно последних 10 реплик для живого непрерывного диалога."""
    history = _CHAT_WINDOWS.setdefault(user_id, [])
    history.append({"role": role, "content": content})
    if len(history) > MAX_WINDOW_MESSAGES:
        _CHAT_WINDOWS[user_id] = history[-MAX_WINDOW_MESSAGES:]


def compress_session_memory(user_id: int, summary_note: str) -> None:
    """Уровень 3: Сжатие истории диалога после записи тренировки в PostgreSQL."""
    _COMPRESSED_CONTEXT[user_id] = summary_note
    _CHAT_WINDOWS[user_id] = []
    _PENDING_PLANS.pop(user_id, None)


def _clean_markdown(text: str) -> str:
    """Убирает звёздочки ** и служебные JSON-блоки из текста ответа для чистого отображения."""
    text = re.sub(r"\[PLAN_JSON\].*?\[/PLAN_JSON\]", "", text, flags=re.DOTALL)
    text = text.replace("**", "").replace("__", "")
    return text.strip()


def _extract_target_date(text: str) -> str | None:
    """Извлекает дату вида '26 число', '26.11', '26 ноября' и возвращает YYYY-MM-DD."""
    now = datetime.now()
    months = {
        "январ": 1, "феврал": 2, "март": 3, "апрел": 4, "ма": 5, "июн": 6,
        "июл": 7, "август": 8, "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12
    }
    m_word = re.search(r"\b(\d{1,2})\s+(январ|феврал|март|апрел|ма|июн|июл|август|сентябр|октябр|ноябр|декабр)[а-яё]*", text.lower())
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

    m_day = re.search(r"\bна\s+(\d{1,2})(?:\s*-?\s*(?:е|ое|го))?\s*(?:числ[оае]?)?\b", text.lower())
    if m_day:
        day = int(m_day.group(1))
        try:
            return datetime(now.year, now.month, day).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _extract_and_store_plan(user_id: int, raw_reply: str, db: Session, target_date: str | None = None) -> str:
    """Извлекает план из [PLAN_JSON] или напрямую из нумерованного списка ответа LLM."""
    normalized = []

    match = re.search(r"\[PLAN_JSON\](.*?)\[/PLAN_JSON\]", raw_reply, flags=re.DOTALL)
    if match:
        try:
            items = json.loads(match.group(1).strip())
            if isinstance(items, list):
                for item in items:
                    raw_name = str(item.get("exercise_name", "")).strip()
                    if not raw_name:
                        continue
                    ex_name = _match_catalog_exercise(raw_name, db) or raw_name
                    normalized.append({
                        "exercise_name": ex_name,
                        "sets": int(item.get("sets", 1)),
                        "reps": int(item.get("reps", 12)),
                        "weight": float(item.get("weight", 0)),
                        "done": bool(item.get("done", False)),
                    })
        except Exception as e:
            print("Plan JSON parse error:", repr(e))

    if not normalized:
        card_pattern = re.finditer(
            r"(?:^|\n)\s*\d+[\.\)]\s*([^\n]+)\n\s*(\d+)\s*(?:подход[а-яё]*\s*)?[×xх*]\s*(\d+)(?:[^\n]*?(\d+(?:[.,]\d+)?)\s*кг)?",
            raw_reply,
            flags=re.IGNORECASE
        )
        for m in card_pattern:
            raw_name = re.sub(r"[\*\#]+", "", m.group(1)).strip()
            if not raw_name:
                continue
            ex_name = _match_catalog_exercise(raw_name, db) or raw_name
            sets = int(m.group(2))
            reps = int(m.group(3))
            weight = float(m.group(4).replace(",", ".")) if m.group(4) else 0.0
            normalized.append({
                "exercise_name": ex_name,
                "sets": sets,
                "reps": reps,
                "weight": weight,
                "done": False,
            })

    if normalized:
        prev_date = _PENDING_PLANS.get(user_id, {}).get("target_date") if isinstance(_PENDING_PLANS.get(user_id), dict) else None
        _PENDING_PLANS[user_id] = {
            "items": normalized,
            "target_date": target_date or prev_date
        }

    return _clean_markdown(raw_reply)



def build_athlete_dossier(user: User, db: Session, muscle_detector) -> dict:
    """Уровень 2: Живой срез состояния атлета из PostgreSQL 17."""
    now = datetime.utcnow()
    workouts = (
        db.query(Workout)
        .filter(Workout.user_id == user.id)
        .order_by(Workout.created_at.desc(), Workout.id.desc())
        .limit(40)
        .all()
    )

    last_trained: dict[str, datetime] = {}
    recent_log = []
    today_items = []
    today_date = now.date()

    for idx, w in enumerate(workouts):
        grp = muscle_detector(w.exercise_name)
        if grp and grp not in last_trained and w.created_at:
            last_trained[grp] = w.created_at
        if idx < 12:
            dt = w.created_at.strftime("%d.%m %H:%M") if w.created_at else "—"
            recent_log.append(f"{dt}: {w.exercise_name} ({w.sets}x{w.reps}, {w.weight or 0} кг)")
        if w.created_at and w.created_at.date() == today_date:
            today_items.append(f"{w.exercise_name} {w.sets}x{w.reps} ({w.weight or 0} кг)")

    recovery_hours_map = {}
    for grp, dt_last in last_trained.items():
        recovery_hours_map[grp] = int((now - dt_last).total_seconds() // 3600)

    total_tonnage = round(sum((w.sets * w.reps * (w.weight or 0)) for w in workouts), 1)

    return {
        "name": user.full_name or user.username,
        "age": user.age,
        "height_cm": user.height_cm,
        "weight_kg": user.weight_kg,
        "target_weight_kg": user.target_weight_kg,
        "goal": user.goal,
        "work_schedule": user.work_schedule,
        "protect_lower_back": bool(user.protect_lower_back),
        "protect_knees": bool(user.protect_knees),
        "protect_elbows": bool(user.protect_elbows),
        "injury_notes": user.injury_notes,
        "today_workouts": today_items,
        "recent_workouts": recent_log,
        "hours_since_muscle_trained": recovery_hours_map,
        "recent_40_tonnage_kg": total_tonnage,
        "compressed_note": _COMPRESSED_CONTEXT.get(user.id, ""),
    }


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


def _get_gigachat_access_token(auth_key: str) -> str | None:
    """Получает и кэширует OAuth-токен GigaChat (действует 30 минут)."""
    now_ts = time.time()
    if _GIGACHAT_TOKEN_CACHE["token"] and now_ts < float(_GIGACHAT_TOKEN_CACHE["expires_at"]) - 60:
        return str(_GIGACHAT_TOKEN_CACHE["token"])

    scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS").strip()
    body = urllib.parse.urlencode({"scope": scope}).encode("utf-8")
    req = urllib.request.Request(
        url="https://" + "ngw.devices.sberbank.ru:9443/api/v2/oauth",
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "Authorization": f"Basic {auth_key}",
        },
        method="POST",
    )
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            token = data.get("access_token", "")
            expires_ms = data.get("expires_at", 0)
            if token:
                _GIGACHAT_TOKEN_CACHE["token"] = token
                _GIGACHAT_TOKEN_CACHE["expires_at"] = (expires_ms / 1000.0) if expires_ms else (now_ts + 1500)
                return token
    except Exception as e:
        print("GigaChat OAuth error:", repr(e))
        return None
    return None

def _call_gigachat_llm(question: str, dossier: dict, window: list[dict], extra_instruction: str = "") -> str | None:
    """Живой человеческий разум на базе GigaChat API (отклик 1-2 сек из Москвы)."""
    auth_key = os.getenv("GIGACHAT_AUTH_KEY", "").strip()
    if not auth_key:
        return None

    access_token = _get_gigachat_access_token(auth_key)
    if not access_token:
        return None

    model_name = os.getenv("GIGACHAT_MODEL", "GigaChat-Max").strip()
    system_prompt = (
        "Ты — живой, мудрый и прямой персональный тренер-напарник в приложении Workout Vault. "
        "Общайся с атлетом на «ты», как равный партнёр и наставник в зале: по делу, без канцелярита, воды и нотаций (протокол Zero-Shame). "
        "СТРОГИЙ ЗАПРЕТ НА MARKDOWN-ЗВЁЗДОЧКИ: никогда не используй символы ** или __ для выделения текста. "
        "Когда к месту для настроя или преодоления усталости после смен — приводи короткие живые примеры или цитаты легенд спорта "
        "(Арнольда Шварценеггера, Мухаммеда Али, Майка Тайсона). "
        "ПРАВИЛА ФИЗИОЛОГИИ И БЕЗОПАСНОСТИ: "
        "- Учитывай досье атлета: возраст, актуальный вес, целевой вес (без урезания углеводов при наборе качественной массы) и недавние тренировки. "
        "- Всегда защищай поясницу, колени и связки локтей (исключай опасные осевые перегрузки и читинг, при дискомфорте сразу предлагай безопасную замену). "
        "- Соблюдай правило 48 часов отдыха для мышечных групп после тяжёлых сессий. "
        "РЕЖИМ 1 — СОСТАВЛЕНИЕ НОВОГО ПЛАНА ТРЕНИРОВКИ: "
        "Выстрой упражнения строго по очереди нумерованным списком:\n"
        "1. Название упражнения\n"
        "   Подходы × Повторы | Рабочий вес | Отдых | Короткий фокус по технике и суставам\n"
        "В конце спроси: «Добавляю эту тренировку в план, да?» и добавь блок [PLAN_JSON]...[/PLAN_JSON].\n"
        "РЕЖИМ 2 — ПРИЁМ ГОТОВОГО ОТЧЁТА О ТРЕНИРОВКЕ ОТ АТЛЕТА: "
        "Если атлет прислал отчёт о уже выполненной тренировке (список упражнений, весов, подходов и повторений), "
        "разбери каждый подход (если повторения в подходах разные, например 14, 16, 16, 12 — запиши каждый подход отдельной позицией с sets=1 и нужным reps), "
        "выведи красивый нумерованный список для сверки и спроси: «Сверь, всё правильно? Переношу эти позиции в План тренировки, чтобы ты мог нажать Записать всю тренировку в БД?» "
        "И в самом конце ответа добавь технический блок строго в таком формате:\n"
        "[PLAN_JSON][{\"exercise_name\": \"Название\", \"sets\": 1, \"reps\": 14, \"weight\": 15.0, \"done\": true}][/PLAN_JSON]\n"
        f"Актуальное досье атлета из PostgreSQL: {json.dumps(dossier, ensure_ascii=False)}. "
        f"{extra_instruction}"
    )

    messages = [{"role": "system", "content": system_prompt}] + window + [{"role": "user", "content": question}]
    payload = json.dumps({
        "model": model_name,
        "messages": messages,
        "temperature": 0.55,
        "max_tokens": 900,
    }).encode("utf-8")

    req = urllib.request.Request(
        url="https://" + "gigachat.devices.sberbank.ru/api/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
        method="POST",
    )
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=14, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("GigaChat Chat error:", repr(e))
        return None


def _is_plan_confirmation(text_low: str) -> bool:
    """Проверяет, подтвердил ли атлет добавление согласованного плана в тренировку."""
    cleaned = re.sub(r"[^\w\sа-яё]", "", text_low).strip()
    if cleaned in CONFIRM_WORDS:
        return True
    prefixes = ("да ", "давай ", "добав", "запиш", "записыв", "перенес", "ок ", "окей ", "хорошо ")
    return any(cleaned.startswith(p) for p in prefixes) and len(cleaned.split()) <= 6



def generate_coach_reply(question: str, user: User, db: Session, muscle_detector) -> dict:
    """
    Живой ИИ-тренер Workout Vault:
    - Общается по-человечески через GigaChat-Max с пошаговой структурой и без звёздочек **;
    - Предлагает план тренировки и добавляет его в список только после подтверждения атлета («Да»);
    - Понимает живую диктовку подходов и обновление веса;
    - Таймер отдыха запускается строго вручную атлетом.
    """
    text = question.strip()
    q = text.lower()
    name = user.full_name or user.username
    dossier = build_athlete_dossier(user, db, muscle_detector)
    window = _CHAT_WINDOWS.get(user.id, [])

    mentioned_date = _extract_target_date(text)

    # 0. Подтверждение ранее предложенного плана тренировки («Да», «Да, на 26 число», «Добавляй»)
    if user.id in _PENDING_PLANS and _is_plan_confirmation(q):
        pending_obj = _PENDING_PLANS.pop(user.id)
        approved_plan = pending_obj["items"] if isinstance(pending_obj, dict) else pending_obj
        plan_date = mentioned_date or (pending_obj.get("target_date") if isinstance(pending_obj, dict) else None)

        unique_names = list(dict.fromkeys(item["exercise_name"] for item in approved_plan))
        ex_names = ", ".join(unique_names)
        date_note = f" на дату {plan_date}" if plan_date else ""
        reply = (
            f"Принято, {name}! Перенёс всё в План тренировки{date_note} ({ex_names}). "
            "Проверь позиции ниже и жми «Записать всю тренировку в БД», когда будешь готов."
        )
        append_session_memory(user.id, "user", text)
        append_session_memory(user.id, "assistant", reply)
        return {
            "mode": "plan_approved",
            "reply": reply,
            "suggested_plan": approved_plan,
            "target_date": plan_date,
        }

    # 1. Обновление веса в диалоге + живая реакция нейросети
    new_weight = parse_weight_update(text)
    if new_weight is not None and 30 <= new_weight <= 300:
        user.weight_kg = new_weight
        db.commit()
        dossier["weight_kg"] = new_weight
        live_reply = _call_gigachat_llm(
            text,
            dossier,
            window,
            extra_instruction=f"Атлет только что обновил свой вес до {new_weight} кг. По-дружески прокомментируй это относительно его Зелёного коридора."
        )
        reply = _clean_markdown(live_reply) if live_reply else f"Принято, {name}! Обновил твой вес до {new_weight} кг."
        append_session_memory(user.id, "user", text)
        append_session_memory(user.id, "assistant", reply)
        return {"mode": "weight_updated", "reply": reply, "weight_kg": new_weight}

    # 2. Распознавание одиночного подхода (только для коротких однострочных реплик, чтобы таблицы шли в LLM)
    is_multiline_table = ("\n" in text) or (len(text) > 95)
    parsed = None if is_multiline_table else parse_workout_command(text)

    if parsed:
        matched_name = _match_catalog_exercise(parsed["exercise_name"], db)
        parsed["exercise_name"] = matched_name

        summary_str = f"{matched_name}: {parsed['summary']['total_sets']} подх., {parsed['summary']['total_reps']} повт., тоннаж {parsed['summary']['tonnage_kg']} кг"
        live_reply = _call_gigachat_llm(
            text,
            dossier,
            window,
            extra_instruction=(
                f"Ты только что занёс в план тренировки атлета выполненную работу ({summary_str}). "
                "Отреагируй как живой опытный напарник: похвали за конкретные цифры, памп или выносливость, "
                "напомни про технику и бережное отношение к суставам. НЕ пиши про автозапуск таймера."
            )
        )
        reply = _clean_markdown(live_reply) if live_reply else (
            f"Красавчик, {name}! Записал в план: {summary_str}. "
            "Отдышись спокойно и запускай таймер сам, когда будешь готов к следующему подходу."
        )
        append_session_memory(user.id, "user", text)
        append_session_memory(user.id, "assistant", reply)
        return {
            "mode": "live_set",
            "reply": reply,
            "workout_entry": parsed,
            "auto_timer_sec": None,
        }

    # 3. Свободный живой разговор с тренером (приветствие, самочувствие, составление плана тренировки)
    llm_answer = _call_gigachat_llm(text, dossier, window)
    if llm_answer:
        clean_reply = _extract_and_store_plan(user.id, llm_answer, db, mentioned_date)
        append_session_memory(user.id, "user", text)
        append_session_memory(user.id, "assistant", clean_reply)
        return {"mode": "llm_ai", "reply": clean_reply}

    # 4. Естественный живой переспрос при временном сбое сети (без сухих заглушек)
    reply = (
        f"Связь в зале чуть моргнула, {name} — повтори, пожалуйста, ещё раз. "
        "Как самочувствие сегодня, что будем качать или какие подходы уже сделал?"
    )
    append_session_memory(user.id, "user", text)
    append_session_memory(user.id, "assistant", reply)
    return {"mode": "smart_engine", "reply": reply}
