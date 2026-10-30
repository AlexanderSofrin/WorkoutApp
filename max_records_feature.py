import tkinter as tk
from models import get_max_records

def open_max_records_window(parent_root):
     """
     Кастомное окно 'Зал Славы' с твоими пиковыми рекордами.
     """
     records_window = tk.Toplevel(parent_root)
     records_window.title("🥇 Зал Славы: Максимальные Рекорды")
     records_window.geometry("400x450")
     records_window.configure(bg="#1e1e1e")
     records_window.grab_set()   # Держим фокус на этом окне

     # Зеленый заголовок
     tk.Label(
            records_window,
            text="ЛИЧНЫЕ РЕКОРДЫ В БОЮ 💪",
            font=("Arial", 14, "bold"),
            fg="#00ff00",
            bg="#1e1e1e"
     ).pack(pady=15)

     # Контейнер для списка рекордов
     list_frame = tk.Frame(records_window, bg="#1e1e1e")
     list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

     # Получаем данные из базы через твой бэкенд
     max_data = get_max_records()

     if not max_data:
                tk.Label(
                   list_frame,
                   text="Рекордов пока нет.\nВремя поднять этот вес! 🏋️‍♂️",
                   font=("Arial", 11, "italic"),
                   fg="#a0a0a0",
                   bg="#1e1e1e"
                  ).pack(pady=50)
     else:
        # Рисуем плашки под каждое упражнение
        for exercise_name, weight in max_data:
                   item_frame = tk.Frame(list_frame, bg="#2a2a2a", bd=1, relief=tk.RIDGE)
                   item_frame.pack(fill=tk.X, pady=4, ipady=6)

                   # Упражнение
                   tk.Label(
                         item_frame,
                         text=f"🔥 {exercise_name}",
                         font=("Arial", 11, "bold"),
                         fg="#ffffff",
                         bg="#2a2a2a"
                        ).pack(side=tk.LEFT, padx=10)

                   # Пиковый вес
                   tk.Label(
                         item_frame,
                         text=f"{weight} кг",
                         font=("Arial", 12, "bold"),
                         fg="#00ff00",
                         bg="#2a2a2a"
                        ).pack(side=tk.RIGHT, padx=10)

     # Кнопка выхода
     tk.Button(
            records_window,
            text="ЗАКРЫТЬ",
            font=("Arial", 10, "bold"),
            fg="#ffffff",
            bg="#ff3333",
            activebackground="#cc0000",
            command=records_window.destroy).pack(pady=15, ipadx=10)