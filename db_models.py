from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base, engine

# Модель таблицы пользователей (Users) + Стартовая анкета атлета (Онбординг)
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Поля стартовой анкеты-приветствия (Онбординг)
    full_name = Column(String(100), nullable=True)          # Как обращаться к атлету
    gender = Column(String(10), nullable=True)              # "male" / "female"
    age = Column(Integer, nullable=True)                    # Возраст
    height_cm = Column(Float, nullable=True)                # Рост в см
    weight_kg = Column(Float, nullable=True)                # Текущий вес в кг
    goal = Column(String(30), default="recomp")             # "cut" (сушка), "recomp" (рекомпозиция), "bulk" (набор)
    work_schedule = Column(String(20), default="2/2")       # График работы: "2/2", "5/2", "free"
    injury_notes = Column(String(255), nullable=True)       # Зоны контроля (например: "поясница, колени, локти")
    is_onboarded = Column(Boolean, default=False)           # Пройдена ли стартовая анкета

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

# Модель таблицы "Умная корзина упражнений" (Exercises)
class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    muscle_group = Column(String(30), nullable=False, index=True)  # chest, back, legs, shoulders, arms, core
    equipment = Column(String(50), default="Гантели")
    technique_tips = Column(String(500), nullable=False)
    common_mistakes = Column(String(500), nullable=True)

    # Флаги травмобезопасности для суставов и позвоночника
    safe_for_lower_back = Column(Boolean, default=True)
    safe_for_knees = Column(Boolean, default=True)
    safe_for_elbows = Column(Boolean, default=True)

    
    sub_group = Column(String(50), nullable=True)              # Детализация: бицепс, трицепс, голень, трапеция и т.д.
    image_url = Column(String(500), nullable=True)            # Фото 1: стартовая позиция
    image_secondary_url = Column(String(500), nullable=True)  # Фото 2: пиковая точка движения
    video_url = Column(String(500), nullable=True)            # Ссылка на видео техники (для этапа витрины)




if __name__ == "__main__":
    print("Создаем таблицы в PostgreSQL...")
    Base.metadata.create_all(bind=engine)
    print("УСПЕХ: Таблицы 'users' и 'workouts' проверены в базе workout_vault!")
