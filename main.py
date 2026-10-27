from ui import WorkoutApp
import models






if __name__ == "__main__":
    models.init_db()   # ← Сначала готовим фундамент: создаём базу и таблицу, если их нет
    app = WorkoutApp() # ← Потом создаём само приложение (окно, кнопки, логику)
    app.mainloop()# ← И запускаем бесконечный цикл, который ждёт действий пользователя

