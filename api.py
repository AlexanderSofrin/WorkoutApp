from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import SessionLocal
from db_models import User, Workout

app = FastAPI(title="Workout Vault Enterprise API", version="2.1.0")

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
    return {"status": "online", "database": "PostgreSQL 17", "version": "2.1.0"}

# 1. Получение всех тренировок пользователя из PostgreSQL
@app.get("/workouts/{user_id}")
def get_user_workouts(user_id: int, db: Session = Depends(get_db)):
    workouts = (
        db.query(Workout)
        .filter(Workout.user_id == user_id)
        .order_by(Workout.created_at.desc())
        .all()
    )
    return {"user_id": user_id, "total_records": len(workouts), "workouts": workouts}

# 2. Аналитика: Поиск личных рекордов (максимальный вес и повторения по каждому упражнению)
@app.get("/workouts/{user_id}/records")
def get_personal_records(user_id: int, db: Session = Depends(get_db)):
    records = (
        db.query(
            Workout.exercise_name,
            func.max(Workout.weight).label("max_weight"),
            func.max(Workout.reps).label("max_reps"),
            func.count(Workout.id).label("total_sessions")
        )
        .filter(Workout.user_id == user_id)
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
    return {"user_id": user_id, "records": result}

# 3. Сохранение новой тренировки напрямую в PostgreSQL
@app.post("/workouts/")
def create_workout(workout: WorkoutCreate, db: Session = Depends(get_db)):
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

# 4. Безопасное удаление записи по ID с проверкой владельца
@app.delete("/workouts/{workout_id}")
def delete_workout(workout_id: int, user_id: int, db: Session = Depends(get_db)):
    workout = db.query(Workout).filter(
        Workout.id == workout_id,
        Workout.user_id == user_id
    ).first()

    if not workout:
        raise HTTPException(status_code=404, detail="Запись не найдена или принадлежит другому пользователю")

    db.delete(workout)
    db.commit()
    return {"status": "deleted", "deleted_id": workout_id}
