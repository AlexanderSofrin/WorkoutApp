import os
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Подгружаем переменные из локального файла .env (если он есть)
load_dotenv()

# 1. Если задан готовый DATABASE_URL (например, внутри Docker-контейнера) — берём его
DATABASE_URL = os.getenv("DATABASE_URL")

# 2. Иначе собираем строку подключения из локальных настроек PostgreSQL 17
if not DATABASE_URL:
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASS = quote_plus(os.getenv("DB_PASSWORD", "ТВОЙ_ПАРОЛЬ"))
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "workout_vault")
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Создаём движок SQLAlchemy с проверкой живости соединений (pool_pre_ping=True — стандарт для Docker)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Фабрика сессий для работы с базой данных
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для декларативных моделей таблиц
Base = declarative_base()
