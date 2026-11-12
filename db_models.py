from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base, engine

# Модель таблицы пользователей (Users)
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связь: у одного пользователя может быть много тренировок
    workouts = relationship("Workout", back_populates="owner")

# Модель таблицы тренировок (Workouts)
class Workout(Base):
    __tablename__ = "workouts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    exercise_name = Column(String(100), nullable=False, index=True)
    sets = Column(Integer, nullable=False)
    reps = Column(Integer, nullable=False)
    weight = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связь: каждая тренировка принадлежит конкретному пользователю
    owner = relationship("User", back_populates="workouts")

# Команда создания таблиц в PostgreSQL при прямом запуске файла
if __name__ == "__main__":
    print("Создаем таблицы в PostgreSQL...")
    Base.metadata.create_all(bind=engine)
    print("УСПЕХ: Таблицы 'users' и 'workouts' созданы в базе workout_vault!")
