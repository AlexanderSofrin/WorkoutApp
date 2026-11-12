import sqlite3
from datetime import datetime, timezone
from database import SessionLocal
from db_models import User, Workout


def parse_date(date_str):
    if not date_str:
        return datetime.now(timezone.utc)
    # Пробуем разные форматы, в которых могла сохраниться дата в SQLite
    for fmt in ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(date_str), fmt)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def migrate():
    sqlite_conn = sqlite3.connect("workout_vault.db")
    sqlite_cursor = sqlite_conn.cursor()
    pg_db = SessionLocal()

    try:
        # 1. Проверяем/переносим пользователей
        sqlite_cursor.execute("PRAGMA table_info(users)")
        user_cols = [col[1] for col in sqlite_cursor.fetchall()]

        sqlite_cursor.execute("SELECT * FROM users")
        old_users = sqlite_cursor.fetchall()

        for row in old_users:
            u = dict(zip(user_cols, row))
            user_id = u.get("id")
            username = u.get("username")
            pwd_hash = u.get("password_hash") or u.get("password") or u.get("pin") or "default_hash"

            exists = pg_db.query(User).filter(User.id == user_id).first()
            if not exists:
                created_dt = parse_date(u.get("created_at"))
                new_user = User(id=user_id, username=username, password_hash=str(pwd_hash), created_at=created_dt)
                pg_db.add(new_user)
        pg_db.commit()
        print(f"Пользователи в базе: {len(old_users)} шт.")

        # 2. Переносим все реальные тренировки
        sqlite_cursor.execute("PRAGMA table_info(workouts)")
        w_cols = [col[1] for col in sqlite_cursor.fetchall()]

        sqlite_cursor.execute("SELECT * FROM workouts")
        old_workouts = sqlite_cursor.fetchall()

        migrated_count = 0
        for row in old_workouts:
            w = dict(zip(w_cols, row))
            w_id = w.get("id")
            ex_name = w.get("exercise_name") or w.get("exercise")

            if ex_name == "string":
                continue  # Пропускаем тестовую запись из Swagger

            exists = pg_db.query(Workout).filter(Workout.id == w_id).first()
            if not exists:
                created_dt = parse_date(w.get("created_at"))
                new_workout = Workout(
                    id=w_id,
                    user_id=w.get("user_id", 1),
                    exercise_name=ex_name,
                    sets=w.get("sets"),
                    reps=w.get("reps"),
                    weight=w.get("weight"),
                    created_at=created_dt
                )
                pg_db.add(new_workout)
                migrated_count += 1

        pg_db.commit()
        print(f"УСПЕХ: Перенесено реальных тренировок в PostgreSQL: {migrated_count} шт.")

    except Exception as e:
        pg_db.rollback()
        print(f"ОШИБКА МИГРАЦИИ: {e}")
    finally:
        sqlite_conn.close()
        pg_db.close()


if __name__ == "__main__":
    migrate()
