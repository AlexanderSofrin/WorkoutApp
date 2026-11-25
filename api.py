from typing import Optional
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from auth import get_db, hash_password, verify_password, create_access_token, get_current_user
from models import init_db
from coach_parser import parse_weight_update, parse_workout_command
from ai_coach import generate_coach_reply
from fastapi.responses import RedirectResponse

from datetime import datetime, timedelta
from db_models import User, Workout, Exercise, DailyNutritionLog
import re

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Workout Vault Enterprise API", version="2.2.0", lifespan=lifespan)
app.mount("/app", StaticFiles(directory="frontend", html=True), name="frontend")



# ==============================================================================================
# PYDANTIC-СХЕМЫ (ВАЛИДАЦИЯ ЗАПРОСОВ И ОТВЕТОВ)
# ==============================================================================================

class UserRegister(BaseModel):
    username: str = Field(min_length=2, max_length=50, description="Логин пользователя")
    password: str = Field(min_length=4, max_length=100, description="Пароль")
    invite_code: str = Field(default="", description="Секретный код приглашения")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_onboarded: bool
    welcome_message: str


class OnboardingRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=100, description="Имя атлета")
    gender: str = Field(pattern="^(male|female)$", description="Пол: male или female")
    age: int = Field(ge=14, le=100, description="Возраст")
    birth_date: str | None = Field(default=None, max_length=20, description="Дата рождения ДД.ММ.ГГГГ")
    height_cm: float = Field(gt=100, lt=250, description="Рост в см")
    weight_kg: float = Field(gt=30, lt=300, description="Текущий вес в кг")
    target_weight_kg: float | None = Field(default=None, gt=30, lt=300, description="Целевой вес (центр Зелёного коридора)")
    goal: str = Field(default="recomp", pattern="^(cut|recomp|bulk)$", description="Цель: cut / recomp / bulk")
    work_type: str = Field(default="mixed", pattern="^(sedentary|mixed|physical)$", description="Характер работы")
    work_schedule: str = Field(default="2/2", description="График работы: 2/2, 5/2 или free")
    workouts_per_week: int = Field(default=3, ge=0, le=14, description="Тренировок в неделю")
    experience_years: float = Field(default=1.0, ge=0, le=50, description="Тренировочный стаж в годах")
    manual_daily_burn: int | None = Field(default=None, ge=1000, le=8000, description="Ручной средний расход ккал/день")

    avatar_url: str | None = Field(default=None, max_length=500, description="Ссылка или путь к фото профиля")
    support_style: str = Field(default="engineering", pattern="^(engineering|gentle|zodiac)$", description="Стиль поддержки")
    protect_lower_back: bool = Field(default=True, description="Беречь поясницу")
    protect_knees: bool = Field(default=True, description="Беречь колени")
    protect_elbows: bool = Field(default=True, description="Беречь локти")
    injury_notes: str | None = Field(default=None, max_length=255, description="Дополнительные заметки по суставам")



class WorkoutCreate(BaseModel):
    exercise_name: str = Field(min_length=1, max_length=100, description="Название упражнения")
    sets: int = Field(gt=0, description="Количество подходов")
    reps: int = Field(gt=0, description="Количество повторений")
    weight: float | None = Field(default=None, ge=0, description="Вес в кг")
    workout_date: str | None = Field(default=None, description="Дата тренировки YYYY-MM-DD (по умолчанию сегодня)")


class ExerciseCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100, description="Название упражнения")
    muscle_group: str = Field(pattern="^(chest|back|legs|shoulders|arms|core)$", description="Группа мышц")
    equipment: str = Field(default="Гантели", max_length=50, description="Оборудование")
    technique_tips: str = Field(min_length=5, max_length=500, description="Ключи правильной техники")
    common_mistakes: str | None = Field(default=None, max_length=500, description="Частые ошибки")
    safe_for_lower_back: bool = Field(default=True, description="Безопасно при чувствительной пояснице")
    safe_for_knees: bool = Field(default=True, description="Безопасно при чувствительных коленях")
    safe_for_elbows: bool = Field(default=True, description="Безопасно при чувствительных локтях")



# ==============================================================================================
# СИСТЕМНЫЙ ЭНДПОИНТ
# ==============================================================================================

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/app")



# ==============================================================================================
# БЛОК АВТОРИЗАЦИИ И ПРИВЕТСТВЕННОЙ АНКЕТЫ (ONBOARDING)
# ==============================================================================================

@app.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserRegister, db: Session = Depends(get_db)):
    required_invite = os.getenv("INVITE_CODE", "EMPIRE2026")
    if user_data.invite_code.strip() != required_invite:
        raise HTTPException(status_code=403, detail="Регистрация закрыта: неверный код приглашения")

    existing = db.query(User).filter(User.username == user_data.username.strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким логином уже существует")

    new_user = User(
        username=user_data.username.strip(),
        password_hash=hash_password(user_data.password),
        is_onboarded=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token(data={"sub": str(new_user.id)})
    return TokenResponse(
        access_token=token,
        is_onboarded=False,
        welcome_message=f"Добро пожаловать в Workout Vault, {new_user.username}! Заполните стартовую анкету (/auth/onboarding) для настройки системы."
    )


@app.post("/auth/login", response_model=TokenResponse)
def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username.strip()).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(data={"sub": str(user.id)})
    greeting_name = user.full_name or user.username
    msg = (
        f"С возвращением, {greeting_name}! Система готова к работе."
        if user.is_onboarded
        else f"Привет, {greeting_name}! Пройдите короткую анкету (/auth/onboarding) для настройки нагрузки и калорий."
    )
    return TokenResponse(access_token=token, is_onboarded=bool(user.is_onboarded), welcome_message=msg)



def _serialize_user_profile(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "gender": user.gender,
        "age": user.age,
        "birth_date": user.birth_date,
        "height_cm": user.height_cm,
        "weight_kg": user.weight_kg,
        "target_weight_kg": user.target_weight_kg,
        "goal": user.goal,
        "work_type": user.work_type,
        "work_schedule": user.work_schedule,
        "workouts_per_week": user.workouts_per_week,
        "avatar_url": user.avatar_url,
        "support_style": user.support_style,
        "protect_lower_back": bool(user.protect_lower_back),
        "protect_knees": bool(user.protect_knees),
        "protect_elbows": bool(user.protect_elbows),
        "injury_notes": user.injury_notes,
        "is_onboarded": bool(user.is_onboarded),
        "experience_years": user.experience_years if user.experience_years is not None else 1.0,
        "manual_daily_burn": user.manual_daily_burn,

    }


def _apply_profile_data(user: User, data: OnboardingRequest) -> None:
    user.full_name = data.full_name.strip()
    user.gender = data.gender
    user.age = data.age
    user.birth_date = data.birth_date.strip() if data.birth_date else None
    user.height_cm = data.height_cm
    user.weight_kg = data.weight_kg
    user.target_weight_kg = data.target_weight_kg if data.target_weight_kg is not None else data.weight_kg
    user.goal = data.goal
    user.work_type = data.work_type
    user.work_schedule = data.work_schedule.strip()
    user.workouts_per_week = data.workouts_per_week
    user.avatar_url = data.avatar_url.strip() if data.avatar_url else None
    user.support_style = data.support_style
    user.protect_lower_back = data.protect_lower_back
    user.protect_knees = data.protect_knees
    user.protect_elbows = data.protect_elbows
    user.injury_notes = data.injury_notes.strip() if data.injury_notes else None
    user.experience_years = data.experience_years
    user.manual_daily_burn = data.manual_daily_burn

    user.is_onboarded = True


@app.post("/auth/onboarding")
def complete_onboarding(
    data: OnboardingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _apply_profile_data(current_user, data)
    db.commit()
    db.refresh(current_user)

    return {
        "status": "success",
        "message": f"Отлично, {current_user.full_name}! Паспорт атлета настроен под график {current_user.work_schedule}.",
        "profile": _serialize_user_profile(current_user)
    }


@app.put("/auth/profile")
def update_my_profile(
    data: OnboardingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Обновление настроек личного кабинета (вес, цель, график, защита суставов, аватар)."""
    _apply_profile_data(current_user, data)
    db.commit()
    db.refresh(current_user)

    return {
        "status": "updated",
        "message": "Настройки личного кабинета успешно сохранены!",
        "profile": _serialize_user_profile(current_user)
    }


@app.get("/auth/me")
def get_my_profile(current_user: User = Depends(get_current_user)):
    return _serialize_user_profile(current_user)



# ==============================================================================================
# ЗАЩИЩЁННЫЕ ЭНДПОИНТЫ ТРЕНИРОВОК (РАБОТАЮТ СТРОГО ПО JWT-ТОКЕНУ)
# ==============================================================================================

@app.get("/workouts/")
def get_my_workouts(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    workouts = (
        db.query(Workout)
        .filter(Workout.user_id == current_user.id)
        .order_by(Workout.created_at.desc())
        .all()
    )
    return {
        "user": current_user.full_name or current_user.username,
        "total_records": len(workouts),
        "workouts": workouts
    }


@app.get("/workouts/records")
def get_personal_records(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    records = (
        db.query(
            Workout.exercise_name,
            func.max(Workout.weight).label("max_weight"),
            func.max(Workout.reps).label("max_reps"),
            func.count(Workout.id).label("total_sessions")
        )
        .filter(Workout.user_id == current_user.id)
        .group_by(Workout.exercise_name)
        .all()
    )

    result = [
        {
            "exercise_name": r.exercise_name,
            "max_weight_kg": r.max_weight if r.max_weight is not None else 0,
            "max_reps": r.max_reps,
            "total_sessions": r.total_sessions
        }
        for r in records
    ]
    return {"user": current_user.full_name or current_user.username, "records": result}


@app.post("/workouts/")
def create_workout(
    workout: WorkoutCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    custom_dt = datetime.utcnow()
    if workout.workout_date:
        try:
            parsed_d = datetime.strptime(workout.workout_date.strip(), "%Y-%m-%d")
            custom_dt = parsed_d.replace(hour=12, minute=0, second=0)
        except ValueError:
            pass

    new_workout = Workout(
        user_id=current_user.id,
        exercise_name=workout.exercise_name,
        sets=workout.sets,
        reps=workout.reps,
        weight=workout.weight,
        created_at=custom_dt
    )
    db.add(new_workout)
    db.commit()
    db.refresh(new_workout)
    return {"status": "saved", "workout": new_workout}


@app.delete("/workouts/{workout_id}")
def delete_workout(
    workout_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    workout = db.query(Workout).filter(
        Workout.id == workout_id,
        Workout.user_id == current_user.id
    ).first()

    if not workout:
        raise HTTPException(status_code=404, detail="Запись не найдена или принадлежит другому пользователю")

    db.delete(workout)
    db.commit()
    return {"status": "deleted", "deleted_id": workout_id}

# ==============================================================================================
# УМНЫЙ ТРЕНЕР (ГЕНЕРАТОР РЕКОМЕНДАЦИЙ НА ОСНОВЕ ВОССТАНОВЛЕНИЯ И ЗАЩИТЫ СУСТАВОВ)
# ==============================================================================================

MUSCLE_LABELS_RU = {
    "chest": "Грудь",
    "back": "Спина",
    "legs": "Ноги",
    "shoulders": "Дельты (Плечи)",
    "arms": "Руки (Бицепс / Трицепс)",
    "core": "Пресс и Кор",
}

# Словарь ключевых слов для автоматического определения группы мышц из архива тренировок
MUSCLE_KEYWORDS = {
    "shoulders": ["дельт", "мах", "протяжк", "армейск", "плеч"],
    "legs": ["присед", "выпад", "гоблет", "ног", "румынск", "станов", "икр", "голен", "квадрицепс", "бедр"],
    "back": ["подтягиван", "тяга", "спин", "широчайш", "шраг", "трапец", "гиперэкстенз"],
    "chest": ["жим лежа", "жим гантелей на наклонной", "отжиман", "брусь", "груд", "сведен", "разводк"],
    "arms": ["бицепс", "трицепс", "французск", "молотки", "подъем на бицепс", "разгибан"],
    "core": ["пресс", "скручиван", "планк", "подъем ног", "вакуум", "кор"],
}


def _detect_muscle_group(exercise_name: str) -> str | None:
    """Определяет мышечную группу по названию упражнения из журнала пользователя."""
    name_lower = exercise_name.lower()
    for group, keywords in MUSCLE_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return group
    return None


@app.get("/workouts/recommend")
def recommend_workout(
    target_muscle: str | None = None,
    location: str | None = None,
    protect_lower_back: bool = False,
    protect_knees: bool = False,
    protect_elbows: bool = False,
    recovery_hours: int = 72,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Умный советник на сегодня:
    1. Проверяет журнал тренировок и таймер восстановления (по умолчанию 72 часа).
    2. Учитывает зоны контроля суставов из профиля (injury_notes) и параметров запроса.
    3. Подбирает оптимальную группу мышц, площадку и безопасные упражнения из Умной корзины.
    """
    now = datetime.utcnow()

    # 1. Автоматически подхватываем заметки о суставах из профиля атлета
    notes = (current_user.injury_notes or "").lower()
    safe_back = protect_lower_back or bool(current_user.protect_lower_back) or ("поясниц" in notes) or ("спин" in notes)
    safe_knees = protect_knees or bool(current_user.protect_knees) or ("колен" in notes)
    safe_elbows = protect_elbows or bool(current_user.protect_elbows) or ("локт" in notes) or ("локот" in notes)

    # 2. Анализируем историю тренировок пользователя для расчёта восстановления
    user_workouts = (
        db.query(Workout)
        .filter(Workout.user_id == current_user.id)
        .order_by(Workout.created_at.desc())
        .limit(100)
        .all()
    )

    last_trained: dict[str, datetime] = {}
    for w in user_workouts:
        group = _detect_muscle_group(w.exercise_name)
        if group and group not in last_trained and w.created_at:
            last_trained[group] = w.created_at

    # Формируем статус готовности по каждой из 6 мышечных групп
    recovery_status = {}
    ready_groups = []
    recovering_groups = []

    for group, ru_name in MUSCLE_LABELS_RU.items():
        if group not in last_trained:
            recovery_status[group] = {
                "muscle_group_ru": ru_name,
                "status": "ready",
                "hours_since_last": None,
                "note": "Давно не тренировалась — полностью готова к работе"
            }
            ready_groups.append((group, 9999))
        else:
            hours_passed = int((now - last_trained[group]).total_seconds() // 3600)
            is_ready = hours_passed >= recovery_hours
            recovery_status[group] = {
                "muscle_group_ru": ru_name,
                "status": "ready" if is_ready else "recovering",
                "hours_since_last": hours_passed,
                "note": (
                    f"Восстановлена (прошло {hours_passed} ч.)"
                    if is_ready
                    else f"На восстановлении (прошло {hours_passed} ч. из {recovery_hours} ч.)"
                )
            }
            if is_ready:
                ready_groups.append((group, hours_passed))
            else:
                recovering_groups.append(ru_name)

    # 3. Определяем целевую группу мышц на сегодня (выбор атлета или совет системы)
    chosen_group = None
    coach_advice = ""

    if target_muscle:
        chosen_group = target_muscle.strip().lower()
        if chosen_group not in MUSCLE_LABELS_RU:
            raise HTTPException(
                status_code=400,
                detail=f"Неизвестная группа мышц. Доступны: {', '.join(MUSCLE_LABELS_RU.keys())}"
            )
        status_info = recovery_status[chosen_group]
        if status_info["status"] == "recovering":
            coach_advice = (
                f"Ты выбрал '{MUSCLE_LABELS_RU[chosen_group]}'. Учти, что эта группа ещё восстанавливается "
                f"({status_info['note']}) — работай в умеренном объёме с запасом 2 повторения до отказа."
            )
        else:
            coach_advice = (
                f"Отличный выбор! Группа '{MUSCLE_LABELS_RU[chosen_group]}' полностью восстановлена и готова к работе."
            )
    else:
        ready_groups.sort(key=lambda item: item[1], reverse=True)
        chosen_group = ready_groups[0][0] if ready_groups else "core"

        recovering_text = (
            f" Сейчас на восстановлении: {', '.join(recovering_groups)}."
            if recovering_groups
            else ""
        )
        coach_advice = (
            f"Оптимальный выбор на сегодня — {MUSCLE_LABELS_RU[chosen_group]} "
            f"({recovery_status[chosen_group]['note']}).{recovering_text} "
            f"Если хочешь прокачать другую группу — просто укажи её в параметре target_muscle."
        )

    # 4. Достаём безопасные упражнения для выбранной группы и площадки из Умной корзины
    ex_query = db.query(Exercise).filter(Exercise.muscle_group == chosen_group)
    if safe_back:
        ex_query = ex_query.filter(Exercise.safe_for_lower_back.is_(True))
    if safe_knees:
        ex_query = ex_query.filter(Exercise.safe_for_knees.is_(True))
    if safe_elbows:
        ex_query = ex_query.filter(Exercise.safe_for_elbows.is_(True))

    if location == "home":
        ex_query = ex_query.filter(
            (Exercise.equipment.ilike("%гантел%")) |
            (Exercise.equipment.ilike("%свой вес%")) |
            (Exercise.equipment.ilike("%коврик%")) |
            (Exercise.equipment.ilike("%резин%"))
        )
    elif location == "street":
        ex_query = ex_query.filter(
            (Exercise.equipment.ilike("%турник%")) |
            (Exercise.equipment.ilike("%брусь%")) |
            (Exercise.equipment.ilike("%перекладин%")) |
            (Exercise.equipment.ilike("%свой вес%"))
        )
    elif location == "gym":
        ex_query = ex_query.filter(
            (Exercise.equipment.ilike("%тренаж%")) |
            (Exercise.equipment.ilike("%блок%")) |
            (Exercise.equipment.ilike("%штанг%")) |
            (Exercise.equipment.ilike("%скамь%")) |
            (Exercise.equipment.ilike("%гантел%"))
        )

    recommended_exercises = ex_query.all()

    return {
        "athlete": current_user.full_name or current_user.username,
        "recommended_muscle_group": chosen_group,
        "recommended_muscle_group_ru": MUSCLE_LABELS_RU[chosen_group],
        "coach_advice": coach_advice,
        "joint_protection_active": {
            "lower_back": safe_back,
            "knees": safe_knees,
            "elbows": safe_elbows
        },
        "recovery_dashboard": recovery_status,
        "suggested_exercises_count": len(recommended_exercises),
        "suggested_exercises": recommended_exercises
    }





# ==============================================================================================
# УМНАЯ КОРЗИНА УПРАЖНЕНИЙ (ЭНЦИКЛОПЕДИЯ ТЕХНИКИ И ТРАВМОБЕЗОПАСНОСТИ)
# ==============================================================================================
SUB_GROUP_LABELS_RU = {
    "delts": "Дельты (Плечи)",
    "traps": "Трапеция",
    "lats": "Широчайшие (Спина)",
    "middle_back": "Середина спины",
    "lower_back": "Поясница",
    "pectorals": "Грудные",
    "quadriceps": "Квадрицепсы (Ноги)",
    "hamstrings": "Бицепс бедра",
    "glutes": "Ягодицы",
    "calves": "Голень (Икры)",
    "biceps": "Бицепс",
    "triceps": "Трицепс",
    "abs": "Пресс и Кор",
}


@app.get("/exercises/categories")
def get_exercise_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Возвращает плитки по основным и детальным группам мышц (плечи, трапеция, бицепс, трицепс, голень и др.) со счётчиками."""
    all_ex = db.query(Exercise).all()
    groups = {}
    sub_groups = {}

    for ex in all_ex:
        g = ex.muscle_group or "other"
        groups[g] = groups.get(g, 0) + 1
        if ex.sub_group:
            sg = ex.sub_group
            sub_groups[sg] = sub_groups.get(sg, 0) + 1

    return {
        "total_exercises": len(all_ex),
        "main_tiles": [
            {"id": key, "title_ru": MUSCLE_LABELS_RU.get(key, key), "count": count}
            for key, count in groups.items()
        ],
        "detailed_sub_tiles": [
            {"id": key, "title_ru": SUB_GROUP_LABELS_RU.get(key, key), "count": count}
            for key, count in sub_groups.items()
        ]
    }


@app.get("/exercises/")
def get_exercises(
    muscle_group: str | None = None,
    protect_lower_back: bool = False,
    protect_knees: bool = False,
    protect_elbows: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Умный подбор упражнений с фильтрацией по группам мышц и защите суставов/поясницы."""
    query = db.query(Exercise)

    if muscle_group:
        query = query.filter(Exercise.muscle_group == muscle_group.strip().lower())
    if protect_lower_back:
        query = query.filter(Exercise.safe_for_lower_back.is_(True))
    if protect_knees:
        query = query.filter(Exercise.safe_for_knees.is_(True))
    if protect_elbows:
        query = query.filter(Exercise.safe_for_elbows.is_(True))

    items = query.order_by(Exercise.muscle_group, Exercise.name).all()
    return {
        "athlete": current_user.full_name or current_user.username,
        "filters_applied": {
            "muscle_group": muscle_group,
            "protect_lower_back": protect_lower_back,
            "protect_knees": protect_knees,
            "protect_elbows": protect_elbows
        },
        "total_found": len(items),
        "exercises": items
    }


@app.post("/exercises/", status_code=status.HTTP_201_CREATED)
def add_exercise(
    ex_data: ExerciseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Добавление нового упражнения в базу знаний Workout Vault."""
    existing = db.query(Exercise).filter(Exercise.name == ex_data.name.strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Такое упражнение уже есть в справочнике")

    new_ex = Exercise(
        name=ex_data.name.strip(),
        muscle_group=ex_data.muscle_group.strip().lower(),
        equipment=ex_data.equipment.strip(),
        technique_tips=ex_data.technique_tips.strip(),
        common_mistakes=ex_data.common_mistakes.strip() if ex_data.common_mistakes else None,
        safe_for_lower_back=ex_data.safe_for_lower_back,
        safe_for_knees=ex_data.safe_for_knees,
        safe_for_elbows=ex_data.safe_for_elbows
    )
    db.add(new_ex)
    db.commit()
    db.refresh(new_ex)

    return {
        "status": "success",
        "message": f"Упражнение '{new_ex.name}' добавлено в Умную корзину!",
        "exercise": new_ex
    }

# ==============================================================================================
# МОДУЛЬ ПИТАНИЯ, КБЖУ И «ЗЕЛЁНОГО КОРИДОРА» ВЕСА (ЭТАП 6)
# ==============================================================================================



@app.get("/nutrition/plan")
def get_nutrition_plan(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Интеллектуальный расчёт КБЖУ и примерного меню на день:
    - учитывает формулу Миффлина — Сан-Жеора, график работы и фактические тренировки за 7 дней;
    - для опытных атлетов поддерживает ручной средний расход (manual_daily_burn);
    - формирует готовый шаблон меню под целевую калорийность без принуждения взвешивать каждый грамм.
    """
    if not current_user.weight_kg or not current_user.height_cm or not current_user.age or not current_user.gender:
        raise HTTPException(
            status_code=400,
            detail="Для расчёта КБЖУ сначала заполните рост, вес, возраст и пол в профиле (/auth/onboarding)."
        )

    weight = current_user.weight_kg
    height = current_user.height_cm
    age = current_user.age
    target_weight = current_user.target_weight_kg or weight
    exp_years = current_user.experience_years if current_user.experience_years is not None else 1.0

    # 1. Базовый обмен веществ (BMR) по формуле Миффлина — Сан-Жеора
    if current_user.gender == "male":
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else:
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161

    # 2. Коэффициент бытовой активности + фактические тренировки из базы за последние 7 дней
    work_factors = {
        "sedentary": 1.25,
        "mixed": 1.40,
        "physical": 1.55,
    }
    base_factor = work_factors.get(current_user.work_type or "mixed", 1.40)

    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_workouts = (
        db.query(Workout)
        .filter(Workout.user_id == current_user.id, Workout.created_at >= week_ago)
        .all()
    )
    # Считаем средний бонус от реальных тренировок за неделю (или плановый, если записей ещё нет)
    if recent_workouts:
        weekly_sets = sum(w.sets for w in recent_workouts)
        weekly_tonnage = sum((w.sets * w.reps * (w.weight or 0)) for w in recent_workouts)
        daily_workout_kcal = round((weekly_sets * 18 + weekly_tonnage * 0.04) / 7)
    else:
        daily_workout_kcal = round(bmr * min((current_user.workouts_per_week or 3) * 0.04, 0.25))

    auto_tdee = round(bmr * base_factor + daily_workout_kcal)

    # Если опытный атлет задал свой расход вручную — опираемся на него
    is_manual_burn = bool(current_user.manual_daily_burn and current_user.manual_daily_burn > 0)
    tdee = current_user.manual_daily_burn if is_manual_burn else auto_tdee

    # 3. Корректировка под цель (щадящий здоровый коридор)
    goal = current_user.goal or "recomp"
    goal_multipliers = {
        "cut": 0.85,      # Бережный дефицит -15% для сохранения мышц
        "recomp": 1.00,   # Поддержание и рекомпозиция
        "bulk": 1.08,     # Плавный чистый профицит +8%
    }
    goal_labels_ru = {
        "cut": "Снижение жировой прослойки (бережный дефицит)",
        "recomp": "Рекомпозиция и рельеф (поддержание веса)",
        "bulk": "Плавный качественный набор массы",
    }

    min_safe_kcal = 1350 if current_user.gender == "female" else 1650
    target_calories = max(round(tdee * goal_multipliers.get(goal, 1.0)), min_safe_kcal)

    # 4. Расчёт белков, жиров и углеводов (в граммах)
    protein_per_kg = 2.0 if goal in ("cut", "recomp") else 1.8
    fat_per_kg = 0.9 if goal == "cut" else 1.0

    protein_g = round(weight * protein_per_kg)
    fat_g = round(weight * fat_per_kg)
    remaining_kcal = max(target_calories - (protein_g * 4 + fat_g * 9), 200)
    carbs_g = round(remaining_kcal / 4)

    # 5. Примерное меню на день под целевой калораж и БЖУ пользователя
    ratio = target_calories / 2000.0
    oats_g = max(round((60 * ratio) / 5) * 5, 35)
    rice_g = max(round((80 * ratio) / 5) * 5, 45)
    meat_g = max(round((170 * ratio) / 10) * 10, 120)
    curd_g = max(round((180 * ratio) / 10) * 10, 120)

    sample_daily_menu = [
        {
            "meal": "Завтрак",
            "kcal": round(target_calories * 0.27),
            "protein_g": round(protein_g * 0.25),
            "items": f"Каша на воде ({oats_g} г сухой крупы) + 3 варёных яйца (или 1 порция протеина)",
        },
        {
            "meal": "Обед",
            "kcal": round(target_calories * 0.35),
            "protein_g": round(protein_g * 0.35),
            "items": f"Рис или гречка ({rice_g} г сухой крупы) + куриная грудка / индейка ({meat_g} г) + свежие овощи",
        },
        {
            "meal": "Полдник",
            "kcal": round(target_calories * 0.16),
            "protein_g": round(protein_g * 0.18),
            "items": f"Творог 5% ({curd_g} г) или протеиновый коктейль + банан / яблоко",
        },
        {
            "meal": "Ужин",
            "kcal": round(target_calories * 0.22),
            "protein_g": round(protein_g * 0.22),
            "items": f"Рыба или нежирное мясо ({max(meat_g - 20, 100)} г) + тушёные овощи или лёгкий салат",
        },
    ]

    # 6. Адаптация под сменный график и «Зелёный коридор» веса
    schedule = current_user.work_schedule or "2/2"
    if schedule == "2/2":
        shift_day_calories = round(target_calories * 1.05)
        rest_day_calories = round(target_calories * 0.95)
        schedule_tip = (
            "График 2/2: в рабочие смены делай упор на сложные углеводы в дневной приём пищи, "
            "а вечерний приём после смены оставляй лёгким (белок + овощи) для глубокого сна."
        )
    else:
        shift_day_calories = target_calories
        rest_day_calories = target_calories
        schedule_tip = "Стандартный график: распределяй сложные углеводы на первую половину дня и до/после тренировки."

    corridor_min = round(target_weight - 1.5, 1)
    corridor_max = round(target_weight + 1.5, 1)
    water_ml = round(weight * 32)
    salt_g = 5.0 if (current_user.workouts_per_week or 0) >= 3 else 4.0

    return {
        "athlete": current_user.full_name or current_user.username,
        "experience_years": exp_years,
        "goal": goal,
        "goal_ru": goal_labels_ru.get(goal, goal),
        "bmr_kcal": round(bmr),
        "tdee_maintenance_kcal": tdee,
        "is_manual_burn": is_manual_burn,
        "daily_workout_bonus_kcal": daily_workout_kcal,
        "daily_target": {
            "calories_kcal": target_calories,
            "protein_g": protein_g,
            "fats_g": fat_g,
            "carbs_g": carbs_g,
        },
        "sample_daily_menu": sample_daily_menu,
        "schedule_adaptation": {
            "work_schedule": schedule,
            "work_day_kcal": shift_day_calories,
            "rest_day_kcal": rest_day_calories,
            "coach_tip": schedule_tip,
        },
        "green_corridor": {
            "current_weight_kg": weight,
            "target_weight_kg": target_weight,
            "safe_range_kg": f"{corridor_min} – {corridor_max} кг",
            "in_corridor": corridor_min <= weight <= corridor_max,
        },
        "hydration_and_electrolytes": {
            "water_ml_per_day": water_ml,
            "salt_g_per_day": salt_g,
            "note": "Соль распределяй на утренний и дневной приёмы пищи, вечером — минимум для защиты от задержки жидкости."
        }
    }


# ==============================================================================================
# МОДУЛЬ «ПСИХОЛОГИЧЕСКИЙ ЩИТ» И ЖИВОЙ ГОЛОС НАСТАВНИКА (ЭТАП 7)
# ==============================================================================================

def _get_zodiac_profile(birth_date_str: str | None) -> dict:
    """Определяет знак зодиака и стихию по дате рождения ДД.ММ.ГГГГ для персонализации тона."""
    if not birth_date_str:
        return {"sign": "Универсальный архетип", "element": "Баланс", "tip": "Двигайся в своём природном ритме без спешки."}
    try:
        parts = birth_date_str.strip().replace("-", ".").replace("/", ".").split(".")
        day, month = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return {"sign": "Универсальный архетип", "element": "Баланс", "tip": "Двигайся в своём природном ритме без спешки."}

    zodiac_table = [
        ((3, 21), (4, 19), "Овен", "Огонь", "Твоя сила в решительном старте, но береги суставы от резких рывков."),
        ((4, 20), (5, 20), "Телец", "Земля", "Твой конёк — железное терпение и системность: шаг за шагом ты строишь мощный фундамент."),
        ((5, 21), (6, 20), "Близнецы", "Воздух", "Разнообразие упражнений и смена акцентов держат твой интерес и лёгкость на высоте."),
        ((6, 21), (7, 22), "Рак", "Вода", "Твоя главная опора — внутреннее спокойствие, защита своего ресурса и сила ради близких."),
        ((7, 23), (8, 22), "Лев", "Огонь", "Личный пример и благородная сила вдохновляют окружающих — держи осанку и уверенный темп."),
        ((8, 23), (9, 22), "Дева", "Земля", "Ювелирная техника, контроль повторений и порядок в цифрах приносят тебе чистый результат."),
        ((9, 23), (10, 22), "Весы", "Воздух", "Гармония между нагрузкой, питанием и глубоким сном — твой главный ключ к прогрессу."),
        ((10, 23), (11, 21), "Скорпион", "Вода", "Мощная внутренняя воля позволяет превращать любое напряжение в чистую энергию роста."),
        ((11, 22), (12, 21), "Стрелец", "Огонь", "Большая созидательная цель зажигает тебя — каждый подход приближает к новой вершине."),
        ((12, 22), (1, 19), "Козерог", "Земля", "Дисциплина и выносливость на длинной дистанции делают тебя непобедимым."),
        ((1, 20), (2, 18), "Водолей", "Воздух", "Свежий взгляд и свобода от шаблонов помогают находить свой уникальный путь в спорте."),
        ((2, 19), (3, 20), "Рыбы", "Вода", "Мягкий вход в тренировку и внимание к сигналам тела дают тебе глубокое восстановление."),
    ]
    for (m1, d1), (m2, d2), sign, element, tip in zodiac_table:
        if (month == m1 and day >= d1) or (month == m2 and day <= d2):
            return {"sign": sign, "element": element, "tip": tip}
    return {"sign": "Козерог", "element": "Земля", "tip": "Дисциплина и выносливость на длинной дистанции делают тебя непобедимым."}


@app.get("/coach/support")
def get_psychological_support(
    tired_after_shift: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Психологический щит Workout Vault:
    - Убирает чувство вины при пропусках (переводит паузу в тактическую разгрузку);
    - Подсвечивает накопленный капитал (общий тоннаж и количество тренировок);
    - Снижает порог входа при усталости после смены;
    - Адаптирует голос наставника под выбранный стиль (engineering / gentle / zodiac).
    """
    now = datetime.utcnow()
    name = current_user.full_name or current_user.username
    style = current_user.support_style or "engineering"

    workouts = (
        db.query(Workout)
        .filter(Workout.user_id == current_user.id)
        .order_by(Workout.created_at.desc())
        .all()
    )

    total_entries = len(workouts)
    total_tonnage = round(sum((w.sets * w.reps * (w.weight or 0)) for w in workouts), 1)
    total_reps = sum((w.sets * w.reps) for w in workouts)

    days_since_last = None
    if workouts and workouts[0].created_at:
        days_since_last = (now.date() - workouts[0].created_at.date()).days

    # 1. Выбираем поведенческий протокол (без чувства вины!)
    if total_entries == 0:
        protocol = "zero_shame_start"
        protocol_title = "Чистый старт без сравнения с другими"
        core_message = (
            f"{name}, любой рекорд в 25–30 подтягиваний всегда начинается с самого первого повторения. "
            "Не смотри по сторонам и не стесняйся стартового уровня — твоя единственная точка отсчёта сегодня это ты сам."
        )
        micro_action = "Выбери 1 базовое упражнение и сделай 2 спокойных подхода с запасом сил."
    elif tired_after_shift:
        protocol = "minimum_action_threshold"
        protocol_title = "Протокол минимального действия после смены"
        core_message = (
            f"{name}, после тяжёлой рабочей смены не нужно бить рекорды — тренировка это не экзекуция, а забота о теле. "
            "Снижаем планку до лёгкой разминки, чтобы сбросить напряжение и сохранить серию без перегруза ЦНС."
        )
        micro_action = "10 минут суставной разминки + 2 лёгких подхода на спину или пресс без отказа."
    elif days_since_last is not None and days_since_last >= 3:
        protocol = "tactical_deload_reframing"
        protocol_title = "Тактическая разгрузка и свежий старт"
        core_message = (
            f"{name}, пауза в {days_since_last} дн. — это не срыв и не повод для самокритики, а осознанная разгрузка суставов и связок. "
            "Никакого чувства вины: открываем новый цикл с чистого листа и возвращаемся в «Зелёный коридор»."
        )
        micro_action = "Начни сегодня с 60–70% от привычного объёма, чтобы мышцы мягко включились в работу."
    else:
        protocol = "steady_creation"
        protocol_title = "Созидательный ритм и гармония"
        core_message = (
            f"{name}, ты идёшь в ровном, зрелом темпе: без надрыва, с уважением к своим связкам и режиму. "
            "Именно из таких спокойных, ежедневных побед складывается настоящая сила и долголетие."
        )
        micro_action = "Отработай плановую группу мышц с чистой техникой (1–2 повторения в запасе) и закрой день качественным сном."

    # 2. Добавляем индивидуальную интонацию под стиль характера
    zodiac_info = _get_zodiac_profile(current_user.birth_date)
    if style == "gentle":
        tone_note = "Мягкий режим: помни, что отдых и восстановление так же важны, как и сама тренировка. Будь к себе добр."
    elif style == "zodiac":
        tone_note = f"Архетип дня ({zodiac_info['sign']}, стихия: {zodiac_info['element']}): {zodiac_info['tip']}"
    else:
        tone_note = "Инженерный фокус: дисциплина без суеты, контроль суставов и плавный рост накопительного капитала."

    return {
        "athlete": name,
        "support_style": style,
        "protocol_active": protocol,
        "protocol_title": protocol_title,
        "mentor_message": core_message,
        "personalized_tone": tone_note,
        "today_micro_step": micro_action,
        "training_progress": {
            "total_workout_records": total_entries,
            "total_tonnage_kg": total_tonnage,
            "total_reps_completed": total_reps,
            "days_since_last_session": days_since_last,
            "note": "Этот капитал уже наработан тобой — он никуда не исчезнет ни при каких паузах."
        }
    }

@app.post("/workouts/claim-legacy")
def claim_legacy_workouts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Привязывает старые записи тренировок без владельца или с user_id=1 к текущему пользователю."""
    orphan_workouts = db.query(Workout).filter(
        (Workout.user_id == None) | (Workout.user_id != current_user.id)
    ).all()
    moved = 0
    for w in orphan_workouts:
        if w.user_id is None or w.user_id == 1:
            w.user_id = current_user.id
            moved += 1
    db.commit()
    return {"status": "ok", "attached_workouts": moved}

class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    current_plan: Optional[list] = None
    scheduled_plans: Optional[dict] = None


class WorkoutCommitRequest(BaseModel):
    exercise_name: str
    entries: list[dict]


@app.post("/coach/chat")
def coach_chat(
    req: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Умный чат-помощник: распознаёт вес, тренировку (создаёт чек-транзакцию) или отмену/исправление."""
    text = req.message.strip()
    lower = text.lower()

    if any(cmd in lower for cmd in ("удали последн", "отмени последн", "ошибка", "убери последн")):
        last_w = (
            db.query(Workout)
            .filter(Workout.user_id == current_user.id)
            .order_by(Workout.created_at.desc(), Workout.id.desc())
            .first()
        )
        if not last_w:
            return {"action": "info", "reply": "В журнале пока нет записей для удаления."}
        deleted_info = f"{last_w.exercise_name} ({last_w.sets}×{last_w.reps}, {last_w.weight or 0} кг)"
        db.delete(last_w)
        db.commit()
        return {
            "action": "deleted",
            "reply": f"Готово! Удалил последнюю запись: {deleted_info}. Счётчики пересчитаны."
        }

    if lower.startswith(("исправь", "поправь", "измени")):
        parsed_fix = parse_workout_command("запиши " + text.split(":", 1)[-1])
        if parsed_fix:
            last_w = (
                db.query(Workout)
                .filter(Workout.user_id == current_user.id)
                .order_by(Workout.created_at.desc(), Workout.id.desc())
                .first()
            )
            if last_w:
                db.delete(last_w)
                db.commit()
            return {
                "action": "confirm_workout",
                "reply": "Старую запись убрал. Проверь обновлённый чек перед сохранением:",
                "transaction": parsed_fix
            }

    new_weight = parse_weight_update(text)
    if new_weight is not None and 30 <= new_weight <= 300:
        current_user.weight_kg = new_weight
        db.commit()
        return {
            "action": "weight_updated",
            "reply": f"Принято! Обновил твой текущий вес до {new_weight} кг и пересчитал норму КБЖУ."
        }

    parsed = parse_workout_command(text)
    if parsed:
        return {
            "action": "confirm_workout",
            "reply": "Сформировал чек тренировки. Всё верно, записываю?",
            "transaction": parsed
        }

    return {
        "action": "info",
        "reply": (
            f"{current_user.full_name or current_user.username}, я на связи! Напиши или надиктуй тренировку "
            "(например: «Гоблет-приседания 25 кг: два по 15, третий 16, четвёртый 20»), обнови вес («Мой вес 67.5») "
            "или скажи «Удали последнюю», если нужно поправить запись."
        )
    }


@app.post("/coach/chat/commit")
def commit_chat_workout(
    tx: WorkoutCommitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Сохраняет подтверждённую транзакцию тренировки в PostgreSQL 17."""
    saved_count = 0
    for item in tx.entries:
        w = Workout(
            user_id=current_user.id,
            exercise_name=tx.exercise_name,
            sets=int(item["sets"]),
            reps=int(item["reps"]),
            weight=float(item.get("weight", 0) or 0)
        )
        db.add(w)
        saved_count += 1
    db.commit()
    return {
        "status": "committed",
        "reply": f"Записано в базу ({saved_count} поз.): {tx.exercise_name}! Общий тоннаж обновлён."
    }

@app.post("/coach/ask")
def ask_personal_ai_coach(
    req: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Персональный ИИ-тренер: живое ведение тренировки, трёхуровневая память и прямое управление БД."""
    result = generate_coach_reply(
        req.message,
        current_user,
        db,
        _detect_muscle_group,
        current_plan=req.current_plan,
        scheduled_plans=req.scheduled_plans
    )

    # Прямое сохранение выполненной тренировки в PostgreSQL по московскому времени
    if result["mode"] == "workout_logged" and result.get("suggested_plan"):
        custom_dt = datetime.utcnow() + timedelta(hours=3)
        if result.get("target_date"):
            try:
                parsed_d = datetime.strptime(result["target_date"], "%Y-%m-%d")
                custom_dt = parsed_d.replace(hour=12, minute=0, second=0)
            except ValueError:
                pass
        for item in result["suggested_plan"]:
            w = Workout(
                user_id=current_user.id,
                exercise_name=item["exercise_name"],
                sets=int(item.get("sets") or 3),
                reps=int(item.get("reps") or 12),
                weight=float(item.get("weight") or 0),
                created_at=custom_dt
            )
            db.add(w)
        db.commit()

    return {
        "athlete": current_user.full_name or current_user.username,
        "mode": result["mode"],
        "reply": result["reply"],
        "workout_entry": result.get("workout_entry"),
        "suggested_plan": result.get("suggested_plan"),
        "target_date": result.get("target_date"),
        "from_date": result.get("from_date"),
        "auto_timer_sec": result.get("auto_timer_sec"),
        "updated_weight_kg": result.get("updated_weight_kg")
    }



class NutritionLogUpsert(BaseModel):
    log_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    target_kcal: int = 0
    consumed_kcal: int = 0
    protein_g: int = 0
    fats_g: int = 0
    carbs_g: int = 0
    weight_kg: float | None = None
    checked_meals_json: str = "[]"


@app.get("/nutrition/logs/{log_date}")
def get_nutrition_log_by_date(
    log_date: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    row = db.query(DailyNutritionLog).filter(
        DailyNutritionLog.user_id == current_user.id,
        DailyNutritionLog.log_date == log_date
    ).first()
    if not row:
        return {"exists": False, "log_date": log_date, "checked_meals_json": "[]", "consumed_kcal": 0}
    return {
        "exists": True,
        "log_date": row.log_date,
        "target_kcal": row.target_kcal,
        "consumed_kcal": row.consumed_kcal,
        "protein_g": row.protein_g,
        "fats_g": row.fats_g,
        "carbs_g": row.carbs_g,
        "weight_kg": row.weight_kg,
        "checked_meals_json": row.checked_meals_json or "[]"
    }


@app.post("/nutrition/logs")
def save_nutrition_log(
    data: NutritionLogUpsert,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    row = db.query(DailyNutritionLog).filter(
        DailyNutritionLog.user_id == current_user.id,
        DailyNutritionLog.log_date == data.log_date
    ).first()
    if not row:
        row = DailyNutritionLog(user_id=current_user.id, log_date=data.log_date)
        db.add(row)

    row.target_kcal = data.target_kcal
    row.consumed_kcal = data.consumed_kcal
    row.protein_g = data.protein_g
    row.fats_g = data.fats_g
    row.carbs_g = data.carbs_g
    row.weight_kg = data.weight_kg
    row.checked_meals_json = data.checked_meals_json
    db.commit()
    return {"status": "saved", "log_date": data.log_date}
