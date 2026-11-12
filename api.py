from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from database import SessionLocal
from db_models import User, Workout

app = FastAPI(title="Workout Vault Enterprise API", version="2.0.0")

# Генератор сессий базы данных (Dependency Injection)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Схема валидации входящей тренировки (Pydantic)
class WorkoutCreate(BaseModel):
    user_id: int = Field(gt=0, description="ID пользователя")
    exercise_name: str = Field(min_length=1, max_length=100, description="Название упражнения")
    sets: int = Field(gt=0, description="Количество подходов")
    reps: int = Field(gt=0, description="Количество повторений")
    weight: float | None = Field(default=None, ge=0, description="Вес в кг")

@app.get("/")
def health_check():
    return {"status": "online", "database": "PostgreSQL 17", "version": "2.0.0"}

# Получение всех тренировок пользователя из PostgreSQL
@app.get("/workouts/{user_id}")
def get_user_workouts(user_id: int, db: Session = Depends(get_db)):
    workouts = (
        db.query(Workout)
        .filter(Workout.user_id == user_id)
        .order_by(Workout.created_at.desc())
        .all()
    )
    return {"user_id": user_id, "total_records": len(workouts), "workouts": workouts}

# Сохранение новой тренировки напрямую в PostgreSQL
@app.post("/workouts/")
def create_workout(workout: WorkoutCreate, db: Session = Depends(get_db)):
    # Проверяем, существует ли такой пользователь в PostgreSQL
    user = db.query(User).filter(User.id == workout.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь с таким ID не найден")

    new_workout = Workout(
        user_id=workout.user_id,
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
