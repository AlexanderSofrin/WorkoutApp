from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func
from db_models import User, Workout, Exercise
from auth import get_db, hash_password, verify_password, create_access_token, get_current_user
from models import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Workout Vault Enterprise API", version="2.2.0", lifespan=lifespan)



# ==============================================================================================
# PYDANTIC-СХЕМЫ (ВАЛИДАЦИЯ ЗАПРОСОВ И ОТВЕТОВ)
# ==============================================================================================

class UserRegister(BaseModel):
    username: str = Field(min_length=2, max_length=50, description="Логин пользователя")
    password: str = Field(min_length=4, max_length=100, description="Пароль")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_onboarded: bool
    welcome_message: str


class OnboardingRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=100, description="Имя атлета")
    gender: str = Field(pattern="^(male|female)$", description="Пол: male или female")
    age: int = Field(ge=14, le=100, description="Возраст")
    height_cm: float = Field(gt=100, lt=250, description="Рост в см")
    weight_kg: float = Field(gt=30, lt=300, description="Текущий вес в кг")
    goal: str = Field(default="recomp", pattern="^(cut|recomp|bulk)$", description="Цель: cut / recomp / bulk")
    work_schedule: str = Field(default="2/2", description="График работы: 2/2, 5/2 или free")
    injury_notes: str | None = Field(default=None, max_length=255, description="Зоны контроля суставов/спины")


class WorkoutCreate(BaseModel):
    exercise_name: str = Field(min_length=1, max_length=100, description="Название упражнения")
    sets: int = Field(gt=0, description="Количество подходов")
    reps: int = Field(gt=0, description="Количество повторений")
    weight: float | None = Field(default=None, ge=0, description="Вес в кг")

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

@app.get("/")
def health_check():
    return {"status": "online", "database": "PostgreSQL 17", "version": "2.2.0", "auth": "JWT Enabled"}


# ==============================================================================================
# БЛОК АВТОРИЗАЦИИ И ПРИВЕТСТВЕННОЙ АНКЕТЫ (ONBOARDING)
# ==============================================================================================

@app.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserRegister, db: Session = Depends(get_db)):
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


@app.post("/auth/onboarding")
def complete_onboarding(
    data: OnboardingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    current_user.full_name = data.full_name.strip()
    current_user.gender = data.gender
    current_user.age = data.age
    current_user.height_cm = data.height_cm
    current_user.weight_kg = data.weight_kg
    current_user.goal = data.goal
    current_user.work_schedule = data.work_schedule.strip()
    current_user.injury_notes = data.injury_notes.strip() if data.injury_notes else None
    current_user.is_onboarded = True

    db.commit()
    db.refresh(current_user)

    return {
        "status": "success",
        "message": f"Отлично, {current_user.full_name}! Твой профиль атлета настроен под график {current_user.work_schedule}.",
        "profile": {
            "id": current_user.id,
            "username": current_user.username,
            "full_name": current_user.full_name,
            "age": current_user.age,
            "height_cm": current_user.height_cm,
            "weight_kg": current_user.weight_kg,
            "goal": current_user.goal,
            "work_schedule": current_user.work_schedule,
            "injury_notes": current_user.injury_notes
        }
    }


@app.get("/auth/me")
def get_my_profile(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "gender": current_user.gender,
        "age": current_user.age,
        "height_cm": current_user.height_cm,
        "weight_kg": current_user.weight_kg,
        "goal": current_user.goal,
        "work_schedule": current_user.work_schedule,
        "injury_notes": current_user.injury_notes,
        "is_onboarded": current_user.is_onboarded
    }


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
    new_workout = Workout(
        user_id=current_user.id,
        exercise_name=workout.exercise_name,
        sets=workout.sets,
        reps=workout.reps,
        weight=workout.weight
    )
    db.add(new_workout)
    db.commit()
    db.refresh(new_workout)

    return {
        "status": "success",
        "message": f"Упражнение '{new_workout.exercise_name}' сохранено в PostgreSQL!",
        "workout_id": new_workout.id
    }


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
# УМНАЯ КОРЗИНА УПРАЖНЕНИЙ (ЭНЦИКЛОПЕДИЯ ТЕХНИКИ И ТРАВМОБЕЗОПАСНОСТИ)
# ==============================================================================================

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
