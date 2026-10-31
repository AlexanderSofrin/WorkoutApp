
import sqlite3 # Подключаем встроенный модуль для работы с базой данных
from datetime import datetime



DB_NAME = "workout_vault.db" # Имя файла нашей базы данных

#Блок работа с базой данных (SQLite)

def get_today_workouts_from_db() -> list:
    # Автоматически определяет текущую дату и забирает тренировки за сегодня
    today_date_str = datetime.now().strftime("%d-%m-%Y")

    conn = None
    try:
        #Открываем бронежилет
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # SQL- запрос использует оператор LIKE, так как в базе к дате пришито время
        query = "SELECT id, created_at, exercise_name, sets, reps, weight FROM workouts WHERE created_at LIKE ? ORDER BY id DESC"
        search_pattern = f"{today_date_str}%"
        cursor.execute(query, (search_pattern,))

        # Забираем все совпадения
        rows = cursor.fetchall()
        return rows
    except sqlite3.Error as e:
        print(f"Ошибка при работе c SQLite: {e}")
        return []

    finally:
        # База закрывается
        if conn:
            conn.close()

def get_unique_exercises() -> list:
    """Извлекает упорядоченный список уникальных названий упражнений для авто продления"""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        query = """
            SELECT DISTINCT exercise_name
            FROM workouts
            WHERE exercise_name IS NOT NULL AND exercise_name != ''
            ORDER BY exercise_name ASC
        """
        cursor.execute(query)

        # Забираем чистые строки из кортежей через [row[0]].
        result = [row[0] for row in cursor.fetchall()]
        return result
    except sqlite3.Error as e:
        print(f"[Ошибка БД при выборке DISTINCT]: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_workouts_by_date_from_db(search_string: str) -> list:
    """Узел 2.  Гибкий поиск по архиву. Ищет любые совпадения по веденной пользователем строке. """
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # Ищем по колонке created_at через LIKE. Сортируем: новые сверху
        query = "SELECT id, created_at, exercise_name, sets, reps, weight FROM workouts WHERE created_at LIKE ? ORDER BY id DESC"
        # Переворачиваем возможный ввод пользователя в другом формате
        search_pattern = f"{search_string}%"
        cursor.execute(query, (search_pattern,))

        rows = cursor.fetchall()
        return rows
    except sqlite3.Error as e:
        print(f"Ошибка при работе с SQLite во время поиска: {e}")
        return []
    finally:
        if conn:
            conn.close()


class WorkoutRecord:
    def __init__(self, exercise: str, sets: int, reps: int, weight: float = None):
        self.exercise_name = exercise.strip()
        self.sets = sets
        self.reps = reps
        self.weight = weight
        self.created_at = datetime.now().strftime("%d-%m-%Y %H:%M:%S")



    def to_summary_string(self) -> str:
        weight_info = f"({self.weight} кг)" if self.weight is not None else ""
        return f"{self.exercise_name}: {self.sets}x{self.reps}{weight_info}"

#==============================================================================================
# Блок работы с базой данных(SQLite) - НАШ ФУНДАМЕНТ
def init_db():
    # Инициализация базы данных.
    # Создает файл базы данных и таблицу тренировок, если их еще нет
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor() # Курсор - это наш "оператор", который выполняет команды
        # Пишем SQL-запрос на создание таблицы (строгие правила для колонок)
        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS workouts ( id INTEGER PRIMARY KEY AUTOINCREMENT,
                   created_at TEXT NOT NULL,
                   exercise_name TEXT NOT NULL, 
                   sets INTEGER NOT NULL,
                   reps INTEGER NOT NULL, 
                   weight REAL ) 
                  """)
        conn.commit()
    except sqlite3.Error as e:
        print(f"Критическая ошибка при инициализации БД: {e}")
        raise  e
    finally:
        if conn:
           conn.close() # Гарантированное закрытие


def save_workout_to_db(workout: WorkoutRecord) -> bool:
    # Принимает объект тренировки и намертво вшивает его в SQLite
    conn = None
    try:

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Вставляем данные через безопасные маркеры
        cursor.execute("""
        INSERT INTO workouts (created_at, exercise_name, sets, reps, weight)
        VALUES (?, ?, ?, ?, ?)
        """, (workout.created_at, workout.exercise_name, workout.sets, workout.reps, workout.weight))
        conn.commit()
        print(f"Запись '{workout.exercise_name}' успешно сохранена в SQLite")
        return True
    except sqlite3.Error as e:
        return False
    finally:
        if conn:
            conn.close()

# Для чтения истории из БД
def get_all_record_from_last_day():
    # Достает из базы данных последние тренировки
    conn = None

    try:
        # Достает из базы данных последние тренировки
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Умный и надежный запрос, учитывающий имя exercise_name и наш формат дат
        cursor.execute("""
                    SELECT created_at, exercise_name, sets, reps, weight
                    FROM workouts
                    WHERE SUBSTR(created_at, 1, 10) = (
                        SELECT SUBSTR(MAX(created_at), 1, 10) FROM workouts
                    )
                    ORDER BY id ASC 
                """)
        rows = cursor.fetchall()#Забираем результаты в виде списка кортежей
        return rows
    except sqlite3.Error as e:
        print(f"Ошибка при чтении из SQLite: {e}")
        return []
    finally:
        if conn:
            conn.close()


#===============================================================================
# Блок первых шагов
#===============================================================================
def validate_workout_data(ex: str, sets_str: str, reps_str: str, weight_str: str):
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

    workout_obj = WorkoutRecord(exercise=ex, sets=sets, reps=reps, weight=weight)
    return True, workout_obj  # возвращаем объект, а не словарь

def get_max_records():
    """
    Вытаскиваем максимальный вес по каждому упражнению за всю историю тренировок.
    """
    # 1. Подключаемся к нашей базе данных
    conn = sqlite3.connect("workout_vault.db")
    cursor = conn.cursor()

    try:
        # Пишем хитрый SQL- запрос с MAX() и GROUP BY
        cursor.execute("""
              SELECT exercise_name, MAX(weight)
              FROM workouts
              WHERE weight IS NOT NULL AND weight > 0
              GROUP BY exercise_name
              ORDER BY MAX(weight) DESC 
        """)
        # 3. Забираем все найденные строки
        return cursor.fetchall()
    except sqlite3.OperationalError:
        # Если таблицы еще нет, возвращаем пустой список, чтобы не было вылета
        return []
    finally:
        # 4. Железно закрываем соединение с базой в любом случае.
         conn.close()



