from datetime import datetime
from sqlalchemy import func, cast, Date
from database import SessionLocal, engine
from db_models import Base, User, Workout

# ==============================================================================================
# БЛОК РАБОТЫ С БАЗОЙ ДАННЫХ (PostgreSQL 17 + SQLAlchemy)
# ==============================================================================================

def _format_dt(dt: datetime) -> str:
    """Переводит дату из PostgreSQL в привычный для интерфейса формат ДД-ММ-ГГГГ ЧЧ:ММ:СС."""
    return dt.strftime("%d-%m-%Y %H:%M:%S") if dt else ""


def get_today_workouts_from_db(user_id: int) -> list:
    """Забирает тренировки за сегодня строго для активного пользователя из PostgreSQL."""
    today_date = datetime.now().date()
    with SessionLocal() as db:
        rows = (
            db.query(Workout)
            .filter(Workout.user_id == user_id, cast(Workout.created_at, Date) == today_date)
            .order_by(Workout.id.desc())
            .all()
        )
        return [(w.id, _format_dt(w.created_at), w.exercise_name, w.sets, w.reps, w.weight) for w in rows]


def get_unique_exercises(user_id: int) -> list:
    """Извлекает список уникальных названий упражнений конкретного пользователя."""
    with SessionLocal() as db:
        rows = (
            db.query(Workout.exercise_name)
            .filter(Workout.user_id == user_id, Workout.exercise_name.isnot(None), Workout.exercise_name != "")
            .distinct()
            .order_by(Workout.exercise_name.asc())
            .all()
        )
        return [row[0] for row in rows]


def get_workouts_by_date_from_db(search_string: str, user_id: int) -> list:
    """Поиск по архиву (по дате ДД-ММ-ГГГГ или тексту) в контуре пользователя."""
    with SessionLocal() as db:
        rows = (
            db.query(Workout)
            .filter(Workout.user_id == user_id)
            .order_by(Workout.id.desc())
            .all()
        )
        result = []
        for w in rows:
            dt_str = _format_dt(w.created_at)
            if dt_str.startswith(search_string):
                result.append((w.id, dt_str, w.exercise_name, w.sets, w.reps, w.weight))
        return result


def init_db():
    """Инициализация таблиц PostgreSQL и базовых профилей кластера."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if not db.query(User).filter(User.id == 1).first():
            db.add(User(id=1, username="Александр", password_hash="default_hash"))
        if not db.query(User).filter(User.id == 2).first():
            db.add(User(id=2, username="Супруга", password_hash="default_hash"))
        db.commit()


def save_workout_to_db(workout, user_id: int) -> bool:
    """Намертво вшивает тренировку в PostgreSQL с жесткой привязкой к user_id."""
    try:
        dt_obj = datetime.strptime(workout.created_at, "%d-%m-%Y %H:%M:%S")
    except ValueError:
        dt_obj = datetime.now()

    with SessionLocal() as db:
        try:
            new_record = Workout(
                user_id=user_id,
                created_at=dt_obj,
                exercise_name=workout.exercise_name,
                sets=workout.sets,
                reps=workout.reps,
                weight=workout.weight
            )
            db.add(new_record)
            db.commit()
            print(f"[БЭКЕНД PG]: Запись '{workout.exercise_name}' сохранена в PostgreSQL для user_id={user_id}")
            return True
        except Exception as e:
            db.rollback()
            print(f"[БЭКЕНД ОШИБКА]: Не удалось сохранить тренировку: {e}")
            return False


def get_all_record_from_last_day(user_id: int):
    """Достает тренировки за самый последний активный день конкретного пользователя."""
    with SessionLocal() as db:
        last_workout = (
            db.query(Workout)
            .filter(Workout.user_id == user_id)
            .order_by(Workout.created_at.desc(), Workout.id.desc())
            .first()
        )
        if not last_workout:
            return []

        last_date = last_workout.created_at.date()
        rows = (
            db.query(Workout)
            .filter(Workout.user_id == user_id, cast(Workout.created_at, Date) == last_date)
            .order_by(Workout.id.asc())
            .all()
        )
        return [(w.id, _format_dt(w.created_at), w.exercise_name, w.sets, w.reps, w.weight) for w in rows]


def update_workout_in_db(workout_id: int, exercise: str, sets: int, reps: int, weight: float) -> bool:
    """Перезаписывает существующую строку в PostgreSQL по ID."""
    with SessionLocal() as db:
        try:
            record = db.query(Workout).filter(Workout.id == workout_id).first()
            if not record:
                return False
            record.exercise_name = exercise.strip()
            record.sets = sets
            record.reps = reps
            record.weight = weight
            db.commit()
            print(f"[БЭКЕНД PG]: Запись с ID {workout_id} обновлена в PostgreSQL.")
            return True
        except Exception as e:
            db.rollback()
            print(f"[БЭКЕНД ОШИБКА]: Не удалось обновить запись в PostgreSQL: {e}")
            return False


def get_max_records(user_id: int = 1):
    """Вытаскивает максимальный вес по каждому упражнению строго для текущего пользователя."""
    with SessionLocal() as db:
        try:
            rows = (
                db.query(Workout.exercise_name, func.max(Workout.weight))
                .filter(Workout.user_id == user_id, Workout.weight.isnot(None), Workout.weight > 0)
                .group_by(Workout.exercise_name)
                .order_by(func.max(Workout.weight).desc())
                .all()
            )
            return [(row[0], row[1]) for row in rows]
        except Exception as e:
            print(f"[БЭКЕНД ОШИБКА]: Не удалось получить рекорды: {e}")
            return []


# ==============================================================================================
# БЛОК ЛОГИКИ И ВАЛИДАЦИИ (БЕЗ ИЗМЕНЕНИЙ)
# ==============================================================================================

class WorkoutRecord:
    def __init__(self, exercise: str, sets: int, reps: int, weight: float = None, custom_date: str = None):
        self.exercise_name = exercise.strip()
        self.sets = sets
        self.reps = reps
        self.weight = weight

        if custom_date:
            current_time = datetime.now().strftime("%H:%M:%S")
            self.created_at = f"{custom_date} {current_time}"
        else:
            self.created_at = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    def to_summary_string(self) -> str:
        weight_info = f"({self.weight} кг)" if self.weight is not None else ""
        return f"{self.exercise_name}: {self.sets}x{self.reps}{weight_info}"


def validate_workout_data(ex: str, sets_str: str, reps_str: str, weight_str: str, custom_date: str = None):
    ex = ex.strip()
    sets_str = sets_str.strip()
    reps_str = reps_str.strip()
    weight_str = weight_str.strip()

    if not ex or not sets_str or not reps_str:
        return False, "Нужно заполнить упражнение, подходы и повторения"

    try:
        sets = int(sets_str)
        reps = int(reps_str)
    except ValueError:
        return False, "Подходы и повторения должны быть целыми числами"

    if sets <= 0 or reps <= 0:
        return False, "Количество подходов и повторений должно быть больше 0"

    weight = None
    if weight_str:
        try:
            weight = float(weight_str.replace(",", "."))
        except ValueError:
            return False, "Вес должен быть числом"

    workout_obj = WorkoutRecord(exercise=ex, sets=sets, reps=reps, weight=weight, custom_date=custom_date)
    return True, workout_obj
