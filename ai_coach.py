import os
import json
import re
import urllib.request
from datetime import datetime
from sqlalchemy.orm import Session
from db_models import User, Workout, Exercise
from coach_parser import parse_workout_command, parse_weight_update

# ==============================================================================================
# ТРЁХУРОВНЕВАЯ БЫСТРАЯ ПАМЯТЬ ИИ-ТРЕНЕРА (Sliding Window + Срез БД + Сжатие)
# ==============================================================================================
_CHAT_WINDOWS: dict[int, list[dict]] = {}
_COMPRESSED_CONTEXT: dict[int, str] = {}
MAX_WINDOW_MESSAGES = 8


def append_session_memory(user_id: int, role: str, content: str) -> None:
    """Уровень 1: Скользящее окно последних 8 реплик для мгновенного отклика (1-2 сек)."""
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


def _call_external_llm(question: str, dossier: dict, window: list[dict]) -> str | None:
    """Вызов быстрой внешней LLM (OpenAI / OpenRouter / DeepSeek / Groq), если задан LLM_API_KEY."""
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        return None

    api_url = os.getenv("LLM_API_URL", "https://openai.com").strip()
    model_name = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()

    system_prompt = (
        "Ты — живой, чуткий персональный ИИ-тренер и напарник в приложении Workout Vault. "
        "Общайся по-товарищески, энергично, коротко (2–4 предложения), без нотаций и чувства вины (Zero-Shame). "
        "Когда атлет диктует подход в реальном времени — подбадривай за прогресс и памп, напоминай про технику "
        "и контроль суставов (поясница, колени, локти) и учитывай восстановление мышц (48–72 ч). "
        f"Актуальный срез из базы атлета: {json.dumps(dossier, ensure_ascii=False)}."
    )

    messages = [{"role": "system", "content": system_prompt}] + window + [{"role": "user", "content": question}]

    payload = json.dumps({
        "model": model_name,
        "messages": messages,
        "temperature": 0.65,
        "max_tokens": 350
    }).encode("utf-8")

    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"]["message"]["content"].strip()
    except Exception:
        return None


def generate_coach_reply(question: str, user: User, db: Session, muscle_detector) -> dict:
    """
    Умный, быстрый ИИ-тренер:
    - Поддерживает живую тренировку подход за подходом (автодобавление в план + автотаймер отдыха);
    - Обновляет вес;
    - Анализирует восстановление, суставы, питание и усталость после смены.
    """
    text = question.strip()
    q = text.lower()
    name = user.full_name or user.username
    dossier = build_athlete_dossier(user, db, muscle_detector)
    window = _CHAT_WINDOWS.get(user.id, [])

    # 1. Обновление веса прямо в диалоге
    new_weight = parse_weight_update(text)
    if new_weight is not None and 30 <= new_weight <= 300:
        user.weight_kg = new_weight
        db.commit()
        reply = f"Принято, {name}! Обновил вес в базе до {new_weight} кг и пересчитал ориентир по калориям."
        append_session_memory(user.id, "user", text)
        append_session_memory(user.id, "assistant", reply)
        return {"mode": "weight_updated", "reply": reply, "weight_kg": new_weight}

    # 2. Живое распознавание подхода / тренировки («сделал первый на дельты 10 кг 18», «гоблет 25 кг 3 по 15» и т.д.)
    parsed = parse_workout_command(text)
    if parsed:
        matched_name = _match_catalog_exercise(parsed["exercise_name"], db)
        parsed["exercise_name"] = matched_name

        # Определяем, нужно ли автоматически запустить таймер отдыха (60 или 90 сек)
        max_reps = max((e["sets"] * e["reps"] if e["sets"] == 1 else e["reps"]) for e in parsed["entries"])
        max_weight = max((e.get("weight") or 0) for e in parsed["entries"])
        rest_sec = 90 if (max_weight >= 20 or "присед" in matched_name.lower() or "подтягив" in matched_name.lower()) else 60

        # Живая реакция напарника на темп и памп
        if max_reps >= 20:
            hype = f"Ого, на {max_reps} повторений — мощно пошёл на памп! Мышцы горят, но держи технику чистой без рывков."
        elif len(window) >= 2:
            hype = "Отличный темп, подход за подходом идёшь чётко! Чувствуй целевую мышцу и береги связки."
        else:
            hype = "Отличное начало, разогрел целевую группу! Подход занёс в план тренировки ниже."

        reply = (
            f"{hype} ({matched_name}: {parsed['summary']['total_sets']} подх., {parsed['summary']['total_reps']} повт.). "
            f"Запускаю таймер отдыха на {rest_sec} сек. — как будешь готов, диктуй следующий!"
        )
        append_session_memory(user.id, "user", text)
        append_session_memory(user.id, "assistant", reply)
        return {
            "mode": "live_set",
            "reply": reply,
            "workout_entry": parsed,
            "auto_timer_sec": rest_sec
        }

    # 3. Если подключена внешняя LLM — даём живой свободный ответ с опорой на трёхуровневую память
    llm_answer = _call_external_llm(text, dossier, window)
    if llm_answer:
        append_session_memory(user.id, "user", text)
        append_session_memory(user.id, "assistant", llm_answer)
        return {"mode": "llm_ai", "reply": llm_answer}

    # 4. Встроенный быстрый аналитический движок (работает мгновенно даже без внешнего API-ключа)
    hours_map = dossier["hours_since_muscle_trained"]
    muscle_ru = {
        "legs": "Ноги", "back": "Спина", "chest": "Грудь",
        "shoulders": "Дельты", "arms": "Руки (бицепс/трицепс)", "core": "Пресс и кор"
    }

    if any(w in q for w in ("что качать", "трениров", "восстанов", "можно ли", "трицепс", "бицепс", "спин", "ног", "груд", "плеч", "дельт")):
        tired = [f"{muscle_ru[g]} ({h} ч.)" for g, h in hours_map.items() if h < 48]
        almost = [f"{muscle_ru[g]} ({h} ч.)" for g, h in hours_map.items() if 48 <= h < 72]
        ready = [muscle_ru[g] for g in muscle_ru if hours_map.get(g, 999) >= 72]

        joints = []
        if dossier["protect_lower_back"]:
            joints.append("поясницу")
        if dossier["protect_knees"]:
            joints.append("колени")
        if dossier["protect_elbows"]:
            joints.append("локти")

        parts = []
        if tired:
            parts.append(f"строго на восстановлении (меньше 48 ч.): {', '.join(tired)}")
        if almost:
            parts.append(f"почти восстановились: {', '.join(almost)}")
        if ready:
            parts.append(f"полностью готовы к работе: {', '.join(ready)}")

            joint_str = f" Контроль суставов активен — бережём {', '.join(joints)}." if joints else ""
            reply = f"{name}, по базе картина такая: {'; '.join(parts)}.{joint_str} Если начинаешь работу — просто надиктуй первый подход!"
        elif any(w in q for w in
                 ("вес", "еда", "питан", "рис", "белок", "калор", "кбжу", "масс", "сушк", "коридор", "кардио",
                  "ходьб")):
            w_now = dossier["weight_kg"] or "—"
            w_goal = dossier["target_weight_kg"] or w_now
            reply = (
                f"{name}, текущий вес {w_now} кг, цель — Зелёный коридор вокруг {w_goal} кг (график {dossier['work_schedule']}). "
                "Если добавил кардио или долгую ходьбу в горку — накинь 150–200 ккал за счёт сложных углеводов (рис/овсянка) днём, "
                "чтобы не уходить в лишний дефицит и беречь мышцы."
            )
        elif any(w in q for w in ("устал", "смен", "нет сил", "тяжело", "спин", "болит", "ноет")):
            reply = (
                f"{name}, услышал тебя! После тяжёлой смены или при скованности в мышцах никаких рекордов — включаем режим заботы о теле: "
                "5 минут мягкой суставной разминки, разгрузка поясницы (ноги на возвышение 90/90) и спокойный сон. Твой тоннаж никуда не убежит!"
            )
        else:
            recent_summary = "; ".join(dossier["recent_workouts"][:2]) if dossier[
                "recent_workouts"] else "сегодня стартуем с чистого листа"
            reply = (
                f"{name}, я на связи и готов вести тренировку подход за подходом! "
                f"Вес: {dossier['weight_kg']} кг, недавние записи: {recent_summary}. "
                "Просто скажи, что сделал (например: «Махи на дельты 10 кг: 18 повторений»), или спроси, какие мышцы уже готовы к бою!"
            )

        append_session_memory(user.id, "user", text)
        append_session_memory(user.id, "assistant", reply)
        return {"mode": "smart_engine", "reply": reply}
