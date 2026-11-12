from fastapi import FastAPI
from pydantic import BaseModel, Field
import models
from fastapi import HTTPException
# Создаем экземпляр веб-приложения
app = FastAPI(title="Workout Vault API", version="1.0.0")

# Схема валидации (замена твоих ручных проверок из models.py!)
class WorkoutCreate(BaseModel):
    user_id: int = Field(gt=0, description="ID пользователя")
    exercise_name: str = Field(min_length=1, description="Название упражнения")
    sets: int = Field(gt=0, description="Количество подходов")
    reps: int = Field(gt=0, description="Количество повторений")
    weight: float | None = Field(default=None, ge=0, description="Вес в кг")

# Первый тестовый адрес (эндпоинт) для проверки связи
@app.get("/")
def health_check():
    return {"status": "online", "project": "Workout Vault Enterprise"}

# Адрес для получения всех тренировок пользователя за последний день
@app.get("/workouts/{user_id}")
def get_last_workouts(user_id: int):
    records = models.get_all_record_from_last_day(user_id)
    return {"user_id": user_id, "workouts": records}


@app.post("/workouts/")
def create_workout(workout: WorkoutCreate):
    # Создаем объект тренировки через твой готовый класс из models.py
    record = models.WorkoutRecord(
        exercise=workout.exercise_name,
        sets=workout.sets,
        reps=workout.reps,
        weight=workout.weight
    )
    # Сохраняем в базу с жесткой привязкой к user_id
    success = models.save_workout_to_db(record, workout.user_id)
    if not success:
        raise HTTPException(status_code=500, detail="Ошибка сохранения в базу данных")

    return {
        "status": "success",
        "message": f"Упражнение '{workout.exercise_name}' записано!",
        "data": record.to_summary_string()
    }