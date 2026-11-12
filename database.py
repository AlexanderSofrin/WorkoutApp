from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Точный адрес твоей новой базы PostgreSQL
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/workout_vault"

# Создаем "движок" (главный кабель связи с базой данных)
engine = create_engine(DATABASE_URL)

# Создаем фабрику сессий (через неё FastAPI будет открывать и закрывать сделки с базой)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс, от которого мы будем создавать таблицы (Users и Workouts)
Base = declarative_base()

# Тестовая проверка связи при прямом запуске файла
if __name__ == "__main__":
    try:
        with engine.connect() as connection:
            print("УСПЕХ: Мост между Python и PostgreSQL (workout_vault) установлен!")
    except Exception as e:
        print(f"ОШИБКА ПОДКЛЮЧЕНИЯ: {e}")
