import sqlite3
from datetime import datetime

DB_NAME = "workout_vault.db"


# ==============================================================================================
# БЛОК РАБОТЫ С БАЗОЙ ДАННЫХ (SQLite) - НАШ ЖЕЛЕЗОБЕТОННЫЙ ФУНДАМЕНТ (РЕФАКТОРИНГ ЧЕРЕЗ WITH)
# ==============================================================================================

def get_today_workouts_from_db(user_id: int) -> list:
    """Забирает тренировки за сегодня строго для активного пользователя."""
    today_date_str = datetime.now().strftime("%d-%m-%Y")

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        query = """
            SELECT id, created_at, exercise_name, sets, reps, weight 
            FROM workouts 
            WHERE user_id = ? AND created_at LIKE ? 
            ORDER BY id DESC
        """
        search_pattern = f"{today_date_str}%"
        cursor.execute(query, (user_id, search_pattern))
        return cursor.fetchall()


def get_unique_exercises(user_id: int) -> list:
    """Извлекает список уникальных названий упражнений конкретного пользователя."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        query = """
            SELECT DISTINCT exercise_name
            FROM workouts
            WHERE user_id = ? AND exercise_name IS NOT NULL AND exercise_name != ''
            ORDER BY exercise_name ASC
        """
        cursor.execute(query, (user_id,))
        return [row[0] for row in cursor.fetchall()]


def get_workouts_by_date_from_db(search_string: str, user_id: int) -> list:
    """Поиск по архиву строго в контуре данных конкретного пользователя."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        query = """
            SELECT id, created_at, exercise_name, sets, reps, weight 
            FROM workouts 
            WHERE user_id = ? AND created_at LIKE ? 
            ORDER BY id DESC
        """
        search_pattern = f"{search_string}%"
        cursor.execute(query, (user_id, search_pattern))
        return cursor.fetchall()


def init_db():
    """Инициализация базы данных, создание пользователей кластера и миграция."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()

        # 1. Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                gender TEXT NOT NULL
            )
        """)

        # 2. Таблица тренировок
        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                exercise_name TEXT NOT NULL, 
                sets INTEGER NOT NULL,
                reps INTEGER NOT NULL, 
                weight REAL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            ) 
        """)

        # --- БЛОК БЕЗОПАСНОЙ МИГРАЦИИ ДАННЫХ ---
        cursor.execute("PRAGMA table_info(workouts)")
        columns = [col[1] for col in cursor.fetchall()]
        if "user_id" not in columns:
            cursor.execute("ALTER TABLE workouts ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")
            conn.commit()
            print("[БЭКЕНД]: Миграция успешна. Колонка user_id добавлена в таблицу workouts.")
        # --------------------------------------

        # 3. Наполнение дефолтными профилями штаба
        cursor.execute("INSERT OR IGNORE INTO users (id, username, gender) VALUES (1, 'Александр', 'male')")
        cursor.execute("INSERT OR IGNORE INTO users (id, username, gender) VALUES (2, 'Супруга', 'female')")

        conn.commit()


def save_workout_to_db(workout, user_id: int) -> bool:
    """Намертво вшивает тренировку в SQLite с жесткой привязкой к user_id."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO workouts (user_id, created_at, exercise_name, sets, reps, weight)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, workout.created_at, workout.exercise_name, workout.sets, workout.reps, workout.weight))
            print(f"Запись '{workout.exercise_name}' успешно сохранена в SQLite для user_id={user_id}")
            return True
    except sqlite3.Error as e:
        print(f"[БЭКЕНД ОШИБКА]: На удалось сохранить тренировку: {e}")
        return False


def get_all_record_from_last_day(user_id: int):
    """Достает тренировки за самый последний активный день конкретного пользователя."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, created_at, exercise_name, sets, reps, weight
            FROM workouts
            WHERE user_id = ? AND SUBSTR(created_at, 1, 10) = (
                SELECT SUBSTR(created_at, 1, 10) FROM workouts WHERE user_id = ? ORDER BY id DESC LIMIT 1
            )
            ORDER BY id ASC
        """, (user_id, user_id))
        return cursor.fetchall()


def update_workout_in_db(workout_id: int, exercise: str, sets: int, reps: int, weight: float) -> bool:
    """Перезаписывает существующую строку (ID уникален, привязка сохраняется автоматически)."""
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


def get_max_records(user_id: int):
    """Вытаскивает максимальный вес по каждому упражнению строго для текущего пользователя."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT exercise_name, MAX(weight)
                FROM workouts
                WHERE user_id = ? AND weight IS NOT NULL AND weight > 0
                GROUP BY exercise_name
                ORDER BY MAX(weight) DESC 
            """, (user_id,))
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
