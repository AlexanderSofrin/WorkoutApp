import sqlite3  # Подключаем встроенный модуль для работы с базой данных
from datetime import datetime

DB_NAME = "workout_vault.db"  # Имя файла нашей базы данных


# ==============================================================================================
# БЛОК РАБОТЫ С БАЗОЙ ДАННЫХ (SQLite) - НАШ ЖЕЛЕЗОБЕТОННЫЙ ФУНДАМЕНТ (РЕФАКТОРИНГ ЧЕРЕЗ WITH)
# ==============================================================================================

def get_today_workouts_from_db() -> list:
    """Автоматически определяет текущую дату и забирает тренировки за сегодня."""
    today_date_str = datetime.now().strftime("%d-%m-%Y")

    # Менеджер контекста with гарантирует закрытие шлюза при любом исходе
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        query = "SELECT id, created_at, exercise_name, sets, reps, weight FROM workouts WHERE created_at LIKE ? ORDER BY id DESC"
        search_pattern = f"{today_date_str}%"
        cursor.execute(query, (search_pattern,))
        return cursor.fetchall()


def get_unique_exercises() -> list:
    """Извлекает упорядоченный список уникальных названий упражнений для автопродления."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        query = """
            SELECT DISTINCT exercise_name
            FROM workouts
            WHERE exercise_name IS NOT NULL AND exercise_name != ''
            ORDER BY exercise_name ASC
        """
        cursor.execute(query)
        return [row[0] for row in cursor.fetchall()]


def get_workouts_by_date_from_db(search_string: str) -> list:
    """Гибкий поиск по архиву. Ищет любые совпадения по введенной пользователем строке."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        query = "SELECT id, created_at, exercise_name, sets, reps, weight FROM workouts WHERE created_at LIKE ? ORDER BY id DESC"
        search_pattern = f"{search_string}%"
        cursor.execute(query, (search_pattern,))
        return cursor.fetchall()


def init_db():
    """Инициализация базы данных. Создает файл БД и таблицу, если их еще нет."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS workouts (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   created_at TEXT NOT NULL,
                   exercise_name TEXT NOT NULL, 
                   sets INTEGER NOT NULL,
                   reps INTEGER NOT NULL, 
                   weight REAL ) 
                  """)
        # conn.commit() выполнится автоматически при выходе из блока with


def save_workout_to_db(workout) -> bool:
    """Принимает объект тренировки и намертво вшивает его в SQLite."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO workouts (created_at, exercise_name, sets, reps, weight)
                VALUES (?, ?, ?, ?, ?)
            """, (workout.created_at, workout.exercise_name, workout.sets, workout.reps, workout.weight))
            print(f"Запись '{workout.exercise_name}' успешно сохранена в SQLite")
            return True
    except sqlite3.Error:
        return False


def get_all_record_from_last_day():
    """Достает из базы данных тренировки за самый последний активный день."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, created_at, exercise_name, sets, reps, weight
            FROM workouts
            WHERE SUBSTR(created_at, 1, 10) = (
                SELECT SUBSTR(created_at, 1, 10) FROM workouts ORDER BY id DESC LIMIT 1
            )
            ORDER BY id ASC
        """)
        return cursor.fetchall()


def update_workout_in_db(workout_id: int, exercise: str, sets: int, reps: int, weight: float) -> bool:
    """Принимает ID записи и новые параметры, намертво перезаписывая строку в SQLite."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            query = """
                UPDATE workouts 
                SET exercise_name = ?, sets = ?, reps = ?, weight = ?
                WHERE id = ?
            """
            cursor.execute(query, (exercise.strip(), sets, reps, weight, workout_id))
            print(f"[БЭКЕНД]: Запись с ID {workout_id} успешно модифицирована в базе.")
            return True
    except sqlite3.Error as e:
        print(f"[БЭКЕНД ОШИБКА]: Не удалось обновить запись в SQLite: {e}")
        return False


def get_max_records():
    """Вытаскиваем максимальный вес по каждому упражнению за всю историю тренировок."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                  SELECT exercise_name, MAX(weight)
                  FROM workouts
                  WHERE weight IS NOT NULL AND weight > 0
                  GROUP BY exercise_name
                  ORDER BY MAX(weight) DESC 
            """)
            return cursor.fetchall()
        except sqlite3.OperationalError:
            return []


# ==============================================================================================
# БЛОК ЛОГИКИ И ВАЛИДАЦИИ
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









