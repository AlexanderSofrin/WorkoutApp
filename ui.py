import tkinter as tk
from tkinter import messagebox
import datetime
import models
from tkinter import simpledialog
# импортируем логику бэкенда из соседнего файла models.py
from models import (validate_workout_data,
                    save_workout_to_db,
                    get_last_five_from_bd,
                    WorkoutRecord,
                    get_today_workouts_from_db)


class WorkoutApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Дневник тренировок")
        self.geometry("750x650")

        self.left_frame = tk.Frame(self)
        self.left_frame.pack(side="left", fill="both", expand=True, padx=20, pady=20)

        self.label_hello = tk.Label(self.left_frame, text="Привет, чемпион!", font=("Arial", 18))
        self.label_hello.pack(pady=40)

        self.msg_label = tk.Label(self.left_frame, text="", fg="#2E7D32", font=("Arial", 12),
                                  justify="left", wraplength=450)
        self.msg_label.pack(pady=10)

        self.sidebar = tk.Frame(self, width=180, bg="#f0f0f0")
        self.sidebar.pack(side="right", fill="y", padx=10, pady=10)

        self.make_sidebar_btn("📝 Записать тренировку", "#4CAF50", "white", self.open_record_window, 10)
        self.make_sidebar_btn("📋 Тренировка за сегодня", "#8E24AA", "white", self.show_today_workouts, 10)
        self.make_sidebar_btn(" 🔍Поиск по дате", "#FF9800", "black", self.open_search_window, 10)
        self.make_sidebar_btn("⏱️ Секундомер и Таймер", "#FFD700", "black", self.open_timer_window, 10)

    def make_sidebar_btn(self, text, bg, fg, command, pady_val=10):
        btn = tk.Button(self.sidebar, text=text, bg=bg, fg=fg,
                        font=("Arial", 11, "bold"), command=command,
                        width=25, anchor="w")
        btn.pack(fill="x", pady=pady_val)
        return btn

    def show_last_five(self):
        try:
            rows = get_last_five_from_bd()

            if not rows:
                self.msg_label.config(text="Пока нет записей о тренировках в базе данных", fg="#E53935")
                messagebox.showinfo("Инфо", "В базе данных пока нет записей.")
                return

            report = "Последние 5 тренировок из (из базы SQLite):\n\n"
            for row in rows:
                date_str, ex, sets, reps, weight = row
                report += f"{date_str}| {ex} | {sets}x{reps}"
                if weight is not None and weight != "":
                    report += f"({weight} кг)\n"
                else:
                    report += "\n"

            self.msg_label.config(text=report, fg="#1565C0")
            messagebox.showinfo("Отчет из БД", report)

        except Exception as e:
            messagebox.showerror("Ошибка базы данных", f"Не удалось прочитать историю из БД: {e} ")

    def show_today_workouts(self):
        """ Метод класса для вывода тренировок за текущий день. """
        try:
            rows = get_today_workouts_from_db()
            today_str = str(datetime.date.today())

            if not rows:
                msg = f"За сегодня ({today_str}) тренировок еще не зафиксировано"
                self.msg_label.config(text=msg, fg="#E53935")
                messagebox.showinfo("Инфо", f"За сегодня({today_str}) записей нет")
                return

            report = f"=== ТРЕНИРОВКИ ЗА СЕГОДНЯ ({today_str}) ===\n\n"
            for row in rows:
                _, date_str, ex, sets, reps, weight = row
                report += f"{ex} | {sets}x{reps} "
                if weight is not None and weight != "":
                    report += f"({weight} кг)\n"
                else:
                    report += "\n"
            self.msg_label.config(text=report, fg="#2E7D32")
            messagebox.showinfo("Сегодняшние тренировки", report)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось получить данные за сегодня: {e}")

    def open_search_window(self):
        """Метод для вызова всплывающего окна и поиска по любой дате в БД."""
        # Вызываем встроенное диалоговое окно ввода текста
        user_input = simpledialog.askstring(
            "Поиск по архиву",
            "Введите дату для поиска,(например, 26-10 или год и месяц)"
        )
        # Если пользователь нажал отмена или закрыл окно просто выходим
        if not user_input:
            return
        # Защищаем случайные пробелы по краям
        user_input = user_input.strip()
        try:
            # Запрашиваем данные из бэкенда models.py по нашему оператору LIKE
            rows = models.get_workouts_by_date_from_db(user_input)
            # Если база вернула пустой список
            if not rows:
                msg = f"🔍По запросу '{user_input}' ничего не найдено в базе."
                self.msg_label.config(text=msg, fg="#E53935")
                messagebox.showinfo("Результаты поиска", msg)
                return

            # Форматируем отчет, если записи не найдены
            report = f"=== РЕЗУЛЬТАТЫ ПОИСКА ДЛЯ: {user_input} ===\n"
            for row in rows:
                # Распаковываем кортеж из БД
                _, date_str, ex, sets, reps, weight = row
                # Обрезаем длинное время, оставляем только ДД-ММ-ГГГГ для красоты
                short_date = date_str[:10]

                report += f"📅{short_date} | {ex} | {sets}x{reps}"
                if weight is not None and weight != "":
                    report += "\n"

            # Выводим результат на экран и дублируем всплывающий отчет
            self.msg_label.config(text=report, fg="#1565C0")
            messagebox.showinfo("Найденные тренировки", report)
        except Exception as e:
            messagebox.showerror("Ошибка поиска", f"Не удалось выполнить поиск: {e}")

    def open_timer_window(self):
        timer_pin = tk.Toplevel(self)
        timer_pin.title("Секундомер и Таймер")
        timer_pin.geometry("350x450")
        # === Блок 1: Секундомер
        seconds = 0
        running = False

        def update_timer():
            nonlocal seconds, running
            if running:
                seconds += 1
                mins, secs = divmod(seconds, 60)
                time_str = f"{mins:02d}:{secs:02d}"
                lbl_time.config(text=time_str)
                timer_pin.after(1000, update_timer)

        def start_timer():
            nonlocal running
            if not running:
                running = True
                update_timer()

        def stop_timer():
            nonlocal running
            running = False

        def reset_timer():
            nonlocal seconds, running
            running = False
            seconds = 0
            lbl_time.config(text="00:00")

        tk.Label(timer_pin, text="⏱ СЕКУНДОМЕР", font=("Arial", 12, "bold"), fg="#1565C0").pack(pady=10)

        lbl_time = tk.Label(timer_pin, text="00:00", font=("Arial", 28, "bold"))
        lbl_time.pack(pady=5)

        btn_frame = tk.Frame(timer_pin)
        btn_frame.pack()

        tk.Button(btn_frame, text="Старт", command=start_timer, width=8).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Стоп", command=stop_timer, width=8).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Сброс", command=reset_timer, width=8).pack(side="left", padx=5)

        # ==== Разделительная линия ====
        canvas = tk.Canvas(timer_pin, height=2, bg="#bdbdbd", highlightthickness=0)
        canvas.pack(fill="x", padx=20, pady=15)

        # ==== Блок 2: Таймеры обратного отсчета
        tk.Label(timer_pin, text="⏲ ТАЙМЕРЫ ОТДЫХА", font=("Arial", 18, "bold"), fg="#1B5E20").pack(pady=10)

        lbl_countdown = tk.Label(timer_pin, text="00:00", font=("Arial", 26, "bold"), fg="#8E24AA")
        lbl_countdown.pack(pady=5)

        # Переменные для контроля обратного отсчета
        countdown_seconds = 0
        countdown_running = False

        def count_down():
            nonlocal countdown_seconds, countdown_running
            # Если таймер остановили извне или время вышло - выходим
            if not countdown_running:
                return

            if countdown_seconds > 0:
                countdown_seconds -= 1
                cmins, csecs = divmod(countdown_seconds, 60)
                lbl_countdown.config(text=f"{cmins:02d}:{csecs:02d}")
                # Рекурсивный вызов через 1 секунду
                timer_pin.after(1000, count_down)
            else:
                countdown_running = False
                # Создаем наше собственное крутое окно вместо messagebox
                alert_win = tk.Toplevel(timer_pin)
                alert_win.title("🏮 КОНТРОЛЬ")
                alert_win.geometry("400x250")
                alert_win.config(bg="#FAFAFA")

                # Поверх всех окон, что бы точно не пропустить
                alert_win.attributes("-topmost", True)

                # Главный грозный заголовок
                tk.Label(
                    alert_win,
                    text="🔴 ОТДЫХ ОКОНЧЕН! 🔴",
                    font=("Arial", 16, "bold"),
                    fg="#D32F2F",
                    bg="#FAFAFA"
                ).pack(pady=15)
                # Структурный рапорт
                report_text = (
                    "========================================  \n"
                    "⚙ СТАТУС: Время отдыха полностью истекло  \n"
                    "🤘 ЦНС: Восстановлена и готова к бою!      \n"
                    "🤾‍♂️ЗАДАЧА: Время фигачить следующий подход!\n"
                    "========================================="
                )
                tk.Label(
                    alert_win,
                    text=report_text,
                    font=("Arial", 11, "bold"),
                    justify="left",
                    fg="#212121",
                    bg="#FAFAFA"
                ).pack(pady=10)

                # Крупная, уверенная кнопка подтверждения
                tk.Button(
                    alert_win,
                    text="В БОЙ!💪",
                    font=("Arial", 12, "bold"),
                    bg="#D32F2F",
                    fg="white",
                    width=15,
                    command=alert_win.destroy
                ).pack(pady=10)

        def start_rest_timer(minutes):
            nonlocal countdown_seconds, countdown_running
            # Сбрасываем старый таймер если он работал
            countdown_running = False

            # Переводим минуты в секунды
            countdown_seconds = int(minutes * 60)

            # Запускаем новый процесс
            countdown_running = True
            cmins, csecs = divmod(countdown_seconds,60)
            lbl_countdown.config(text=f"{cmins:02d}:{csecs:02d}")
            count_down()

        def stop_rest_timer():
            nonlocal countdown_running
            countdown_running = False
            lbl_countdown.config(text="00:00")

        # Панель кнопок интервального отдыха
        rest_btn_frame = tk.Frame(timer_pin)
        rest_btn_frame.pack(pady=10)

        # Используем lambda, чтобы передавать аргументы внутрь функции без автозапуска!
        tk.Button(rest_btn_frame,text="1 минута", width=8, bg="#C8E6C9", command=lambda: start_rest_timer(1)).pack(side="left", padx=5)
        tk.Button(rest_btn_frame, text="1.5 минуты", width=8, bg="#C8E6C9", command=lambda: start_rest_timer(1.5)).pack(side="left", padx=5)
        tk.Button(rest_btn_frame, text="2 минуты", width=8, bg="#C8E6C9", command=lambda: start_rest_timer(2)).pack(side="left", padx=5)

        # Кнопка экстренного сброса таймера
        tk.Button(timer_pin, text="Сброс", width=18, bg="#FFCDD2", command=stop_rest_timer).pack(pady=10)


    def open_record_window(self):
        win = tk.Toplevel(self)
        win.title("Новая тренировка")
        win.geometry("450x350")

        tk.Label(win, text="Упражнение:").pack()
        e_ex = tk.Entry(win, width=40)
        e_ex.pack(pady=5)

        tk.Label(win, text="Подходы (число):").pack()
        e_sets = tk.Entry(win, width=20)
        e_sets.pack(pady=5)

        tk.Label(win, text="Повторения (число):").pack()
        e_reps = tk.Entry(win, width=20)
        e_reps.pack(pady=5)

        tk.Label(win, text="Вес (кг):").pack()
        e_weight = tk.Entry(win, width=20)
        e_weight.pack(pady=5)

        def save_and_close():
            raw_ex = e_ex.get()
            raw_sets = e_sets.get()
            raw_reps = e_reps.get()
            raw_weight = e_weight.get()

            success, result = validate_workout_data(raw_ex, raw_sets, raw_reps, raw_weight)
            if not success:
                messagebox.showwarning("Внимание", result)
                return

            # result — это объект WorkoutRecord, передаём его целиком
            try:
                save_workout_to_db(result)
                self.msg_label.config(text=f"Записано: {result.exercise_name}, {result.sets}x{result.reps}")
                messagebox.showinfo("Готово", "Тренировка успешно сохранена в базу данных!")
                win.destroy()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить: {e}")

        btn_save = tk.Button(win, text="Сохранить", bg="#4CAF50", fg="white",
                             font=("Arial", 12, "bold"), command=save_and_close)
        btn_save.pack(pady=20)
