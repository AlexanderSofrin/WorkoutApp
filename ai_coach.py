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
# ТРЁХУРОВНЕВАЯ БЫСТРАЯ ПАМЯТЬ ИИ-ТРЕНЕРА (Sliding Window + Срез БД + Сжатие)
# ==============================================================================================
_CHAT_WINDOWS: dict[int, list[dict]] = {}
_COMPRESSED_CONTEXT: dict[int, str] = {}
MAX_WINDOW_MESSAGES = 10

_GIGACHAT_TOKEN_CACHE: dict[str, str | float] = {"access_token": "", "expires_at": 0.0}


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
        if idx < 8:
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


_GIGACHAT_TOKEN_CACHE: dict[str, object] = {"token": "", "expires_at": 0.0}


def _get_gigachat_access_token(auth_key: str) -> str | None:
    """Получает и кэширует OAuth-токен GigaChat (действует 30 минут)."""
    now_ts = time.time()
    if _GIGACHAT_TOKEN_CACHE["token"] and now_ts < float(_GIGACHAT_TOKEN_CACHE["expires_at"]) - 60:
        return str(_GIGACHAT_TOKEN_CACHE["token"])

    scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS").strip()
    body = urllib.parse.urlencode({"scope": scope}).encode("utf-8")
    req = urllib.request.Request(
        url="https://sberbank.ru",

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
        "Ты — живой, душевный и умный персональный тренер-напарник в приложении Workout Vault. "
        "Общайся с атлетом как настоящий близкий друг и опытный наставник в зале: тепло, естественно, с лёгким юмором, "
        "без канцелярита, списков со звёздочками и нотаций (протокол Zero-Shame). Когда к месту для настроя или "
        "поддержки после тяжёлой смены — приводи короткие живые примеры или мысли легенд спорта (Арнольда Шварценеггера, "
        "Мухаммеда Али, Майка Тайсона). Отвечай ёмко (2–4 живых предложения). "
        "Опирайся на актуальное досье атлета из базы (вес, суставы, усталость, недавние тренировки): "
        f"{json.dumps(dossier, ensure_ascii=False)}. "
        f"{extra_instruction}"
    )

    messages = [{"role": "system", "content": system_prompt}] + window + [{"role": "user", "content": question}]
    payload = json.dumps({
        "model": model_name,
        "messages": messages,
        "temperature": 0.75,
        "max_tokens": 400,
    }).encode("utf-8")

    req = urllib.request.Request(
        url="https://sberbank.ru",

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
        with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("GigaChat Chat error:", repr(e))
        return None

def generate_coach_reply(question: str, user: User, db: Session, muscle_detector) -> dict:
    """
    Живой ИИ-тренер Workout Vault:
    - Общается по-человечески через GigaChat API с опорой на трёхуровневую память;
    - Понимает живую диктовку подходов (1 подход или серию из 3-4 подходов) и добавляет их в план;
    - Таймер отдыха НЕ запускает принудительно — атлет включает его сам, когда удобно.
    """
    text = question.strip()
    q = text.lower()
    name = user.full_name or user.username
    dossier = build_athlete_dossier(user, db, muscle_detector)
    window = _CHAT_WINDOWS.get(user.id, [])

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
            extra_instruction=f"Атлет только что обновил свой вес в базе до {new_weight} кг. По-дружески прокомментируй это относительно его Зелёного коридора."
        )
        reply = live_reply or f"Принято, {name}! Обновил вес в базе до {new_weight} кг и пересчитал ориентир по калориям."
        append_session_memory(user.id, "user", text)
        append_session_memory(user.id, "assistant", reply)
        return {"mode": "weight_updated", "reply": reply, "weight_kg": new_weight}

    # 2. Распознавание подхода или серии из 3-4 подходов + живая человеческая реакция тренера
    parsed = parse_workout_command(text)
    if parsed:
        matched_name = _match_catalog_exercise(parsed["exercise_name"], db)
        parsed["exercise_name"] = matched_name

        summary_str = f"{matched_name}: {parsed['summary']['total_sets']} подх., {parsed['summary']['total_reps']} повт., тоннаж {parsed['summary']['tonnage_kg']} кг"
        live_reply = _call_gigachat_llm(
            text,
            dossier,
            window,
            extra_instruction=(
                f"Ты только что автоматически занёс в план тренировки атлета выполненную работу ({summary_str}). "
                "Отреагируй как живой опытный напарник: похвали за конкретные цифры, памп или выносливость, "
                "напомни про технику и бережное отношение к суставам. НЕ пиши про автозапуск таймера."
            )
        )
        reply = live_reply or (
            f"Красавчик, {name}! Записал в план: {summary_str}. "
            "Отдышись спокойно и запускай таймер сам, когда будешь готов к следующему подходу!"
        )
        append_session_memory(user.id, "user", text)
        append_session_memory(user.id, "assistant", reply)
        return {
            "mode": "live_set",
            "reply": reply,
            "workout_entry": parsed,
            "auto_timer_sec": None
        }

    # 3. Свободный живой разговор с тренером на любую тему (приветствие, самочувствие, питание, план)
    llm_answer = _call_gigachat_llm(text, dossier, window)
    if llm_answer:
        append_session_memory(user.id, "user", text)
        append_session_memory(user.id, "assistant", llm_answer)
        return {"mode": "llm_ai", "reply": llm_answer}

    # 4. Запасной локальный движок (сработает только если в Amvera не задан GIGACHAT_AUTH_KEY)
    reply = (
        f"Привет, {name}! Я на связи и готов вести тренировку подход за подходом. "
        f"Сейчас в базе твой вес {dossier['weight_kg']} кг. Расскажи, как самочувствие после смены, "
        "или просто продиктуй сделанные подходы!"
    )
    append_session_memory(user.id, "user", text)
    append_session_memory(user.id, "assistant", reply)
    return {"mode": "smart_engine", "reply": reply}
