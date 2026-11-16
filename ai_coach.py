import os
import json
import urllib.request
from datetime import datetime
from sqlalchemy.orm import Session
from db_models import User, Workout, Exercise


def build_athlete_dossier(user: User, db: Session, muscle_detector) -> dict:
    """Собирает полное актуальное досье атлета из PostgreSQL 17 для ИИ-тренера."""
    now = datetime.utcnow()
    workouts = (
        db.query(Workout)
        .filter(Workout.user_id == user.id)
        .order_by(Workout.created_at.desc(), Workout.id.desc())
        .limit(50)
        .all()
    )

    last_trained: dict[str, datetime] = {}
    recent_log = []
    for idx, w in enumerate(workouts):
        grp = muscle_detector(w.exercise_name)
        if grp and grp not in last_trained and w.created_at:
            last_trained[grp] = w.created_at
        if idx < 8:
            dt = w.created_at.strftime("%d.%m %H:%M") if w.created_at else "—"
            recent_log.append(f"{dt}: {w.exercise_name} ({w.sets}x{w.reps}, {w.weight or 0} кг)")

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
        "recent_workouts": recent_log,
        "hours_since_muscle_trained": recovery_hours_map,
        "recent_50_tonnage_kg": total_tonnage,
    }


def _call_external_llm(question: str, dossier: dict) -> str | None:
    """
    Если в .env задан LLM_API_KEY (OpenAI / OpenRouter / DeepSeek / локальный Ollama),
    отправляет вопрос и досье в настоящую языковую модель.
    """
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        return None

    api_url = os.getenv("LLM_API_URL", "https://openai.com").strip()
    model_name = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()

    system_prompt = (
        "Ты — персональный ИИ-тренер и нутрициолог в приложении Workout Vault. "
        "Общайся по-дружески, чётко, без воды и осуждения. Опирайся на реальные данные из досье атлета: "
        f"{json.dumps(dossier, ensure_ascii=False)}. "
        "Всегда учитывай защиту его суставов (поясница, колени, локти) и таймер восстановления мышц (72 часа)."
    )

    payload = json.dumps({
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ],
        "temperature": 0.6,
        "max_tokens": 450
    }).encode("utf-8")

    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def generate_coach_reply(question: str, user: User, db: Session, muscle_detector) -> dict:
    """Генерирует глубокий персональный ответ тренера (через LLM API или встроенный движок аналитики)."""
    dossier = build_athlete_dossier(user, db, muscle_detector)

    # 1. Пробуем внешнюю LLM, если настроен ключ в .env
    llm_answer = _call_external_llm(question, dossier)
    if llm_answer:
        return {"mode": "llm_ai", "reply": llm_answer}

    # 2. Встроенный интеллектуальный движок тренера (работает автономно по данным из PostgreSQL 17)
    q = question.lower()
    name = dossier["name"]
    hours_map = dossier["hours_since_muscle_trained"]

    muscle_ru = {
        "legs": "Ноги", "back": "Спина", "chest": "Грудь",
        "shoulders": "Дельты", "arms": "Руки (бицепс/трицепс)", "core": "Пресс и кор"
    }

    # Вопрос про восстановление / что качать / можно ли добавить группу
    if any(w in q for w in ("что качать", "трениров", "восстанов", "можно ли", "трицепс", "бицепс", "спин", "ног", "груд", "плеч", "дельт")):
        tired = [f"{muscle_ru[g]} (прошло {h} ч.)" for g, h in hours_map.items() if h < 72]
        ready = [muscle_ru[g] for g in muscle_ru if hours_map.get(g, 999) >= 72]

        joints = []
        if dossier["protect_lower_back"]:
            joints.append("поясницу")
        if dossier["protect_knees"]:
            joints.append("колени")
        if dossier["protect_elbows"]:
            joints.append("локти")
        joint_str = f"Помним про защиту: бережём {', '.join(joints)}. " if joints else ""

        tired_str = f"Сейчас ещё на восстановлении: {', '.join(tired)}. " if tired else "Все мышечные группы полностью отдохнули! "
        ready_str = f"Полностью готовы к работе: {', '.join(ready)}. " if ready else ""

        last_info = f"Последняя запись в журнале: {dossier['recent_workouts'][0]}." if dossier["recent_workouts"] else ""
        return {
            "mode": "smart_engine",
            "reply": f"{name}, смотрю твою базу: {tired_str}{ready_str}{joint_str}{last_info}"
        }

    # Вопрос про питание, вес, массу, сушку
    if any(w in q for w in ("вес", "еда", "питан", "рис", "белок", "калор", "кбжу", "масс", "сушк", "коридор")):
        w_now = dossier["weight_kg"] or "не указан"
        w_goal = dossier["target_weight_kg"] or w_now
        sched = dossier["work_schedule"] or "2/2"
        return {
            "mode": "smart_engine",
            "reply": (
                f"{name}, твой текущий вес {w_now} кг при цели {w_goal} кг (график {sched}). "
                "Держи вес в Зелёном коридоре (±1,5 кг от цели): в рабочие смены делай упор на сложные углеводы днём, "
                "а вечером оставляй лёгкий белковый приём пищи. Если вес стоит 2 недели — добавь 50–100 г крупы в обед."
            )
        }

    # Вопрос про усталость / смену / мотивацию
    if any(w in q for w in ("устал", "смен", "нет сил", "тяжело", "лень", "отдохн")):
        return {
            "mode": "smart_engine",
            "reply": (
                f"{name}, после тяжёлой смены главная задача — не рекорды, а сохранение ресурса и здоровый сон. "
                "Сделай 10 минут лёгкой суставной разминки или просто отдохни: в твоём активе уже солидный тоннаж, "
                "и один спокойный день восстановления только укрепит связки."
            )
        }

    # Универсальный разбор текущей формы
    recent_summary = "; ".join(dossier["recent_workouts"][:3]) if dossier["recent_workouts"] else "пока нет свежих записей"
    return {
        "mode": "smart_engine",
        "reply": (
            f"{name}, я вижу твою актуальную форму: вес {dossier['weight_kg']} кг, график {dossier['work_schedule']}. "
            f"Последние сессии: {recent_summary}. "
            "Спроси меня, какие мышцы уже восстановились, как скорректировать питание или какие упражнения выбрать с защитой суставов!"
        )
    }
