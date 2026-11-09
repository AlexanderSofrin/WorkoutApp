import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import models
from strings import LANGUAGES
from  auth_window import AuthWindow
from tkcalendar import Calendar
import datetime
from tkinter import simpledialog
from max_records_feature import open_max_records_window
# импортируем логику бэкенда из соседнего файла models.py
from models import (validate_workout_data,
                    save_workout_to_db,
                    update_workout_in_db,
                    get_all_record_from_last_day,
                    WorkoutRecord,
                    get_today_workouts_from_db,
                    get_unique_exercises)


class WorkoutApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Дневник тренировок")
        self.geometry("750x650")

        # 1. Железно прячем главное окно в фон на старте сессии
        self.withdraw()

        # 2. Инициализируем переменные базовыми значениями (всё сохранено!)
        self.active_user = "Александр"
        self.current_lang = "ru"
        self.all_exercises = get_unique_exercises()
        self.current_search_date = datetime.datetime.now().strftime("%d-%m-%Y")

        # 3. Вызываем стартовое окно авторизации сессии
        AuthWindow(self, self.start_main_session)



    def start_main_session(self, user_name, lang):
        """Callback-метод: принимает данные из шлюза авторизации и разворачивает интерфейс"""
        self.active_user = user_name
        self.current_lang = lang  # Фиксируем выбор пользователя

        # Подтягиваем нужный языковой пакет из strings.py
        lang_pack = LANGUAGES[self.current_lang]

        # Строим архитектурные слои интерфейса
        self.left_frame = tk.Frame(self)
        self.left_frame.pack(side="left", fill="both", expand=True, padx=20, pady=20)

        self.label_hello = tk.Label(self.left_frame, text=lang_pack["hello"], font=("Arial", 18), fg="black")
        self.label_hello.pack(pady=40)

        self.msg_label = tk.Label(self.left_frame, text="", fg="#2E7D32", font=("Arial", 12),
                                  justify="left", wraplength=450)
        self.msg_label.pack(pady=10)

        self.sidebar = tk.Frame(self, width=180, bg="#f0f0f0")
        self.sidebar.pack(side="right", fill="y", padx=10, pady=10)

        # Прошиваем динамический текст кнопок из словаря strings.py
        self.make_sidebar_btn(lang_pack["btn_record"], "#4CAF50", "white", self.open_record_window, 10)
        self.make_sidebar_btn(lang_pack["btn_last_workout"], "#8E24AA", "white", self.show_today_workouts, 10)
        self.make_sidebar_btn(lang_pack["btn_search"], "#FF9800", "black", self.open_search_window, 10)
        self.make_sidebar_btn(lang_pack["btn_timer"], "#FFD700", "black", self.open_timer_window, 10)
        self.make_sidebar_btn(text=lang_pack["btn_records"], bg="#00ff00", fg="black",
                              command=lambda: open_max_records_window(self))

        # Выводим главное окно из фона на передний план во всей красе!
        self.deiconify()

    def make_sidebar_btn(self, text, bg, fg, command, pady_val=10):
        btn = tk.Button(self.sidebar, text=text, bg=bg, fg=fg,
                        font=("Arial", 11, "bold"), command=command,
                        width=25, anchor="w")
        btn.pack(fill="x", pady=pady_val)
        return btn

    def show_last_five(self):
        try:
            rows = get_all_record_from_last_day()

            if not rows:
                self.msg_label.config(text="Пока нет записей о тренировках в базе данных", fg="#E53935")
                messagebox.showinfo("Инфо", "В базе данных пока нет записей.")
                return

            report = "Последняя тренировка из (из базы SQLite):\n\n"

            for row in rows:

                _, date_str, ex, sets, reps, weight = row
                report += f"{date_str} | {ex} | {sets}x{reps}"
                if weight is not None and weight != "":
                    report += f" ({weight} кг)\n"
                else:
                    report += "\n"

            self.msg_label.config(text=report, fg="#1565C0")
            # Запоминаем дату, которую успешно нашёл пользователь
            if "ДЛЯ:" in report:
                self.current_search_date = report.split("ДЛЯ:")[1].split("===")[0].strip()

            # Перерисовываем благородную графитовую кнопку под архивный поиск
            if hasattr(self, 'btn_edit_hub') and self.btn_edit_hub.winfo_exists():
                self.btn_edit_hub.destroy()

            self.btn_edit_hub = tk.Button(
                self.left_frame,
                text="✏️ Управление записями дневника",
                bg="#37474F", fg="white", font=("Arial", 11, "bold"),
                command=self.open_edit_hub_window
            )
            self.btn_edit_hub.pack(pady=15, fill="x")

            # Железный фикс: силой заставляем интерфейс отобразить кнопку до вызова окна
            self.update_idletasks()

            # Дублируем всплывающий отчет
            messagebox.showinfo("Найденные тренировки", report)

        except Exception as e:
            messagebox.showerror("Ошибка поиска", f"Не удалось выполнить поиск: {e}")


    def show_today_workouts(self):
            try:
                # Автоматически подтягиваем дату САМОЙ ПОСЛЕДНЕЙ физической записи из базы
                self.current_search_date = models.get_all_record_from_last_day()[0][1][:10] if models.get_all_record_from_last_day() else datetime.datetime.now().strftime("%d-%m-%Y")



                # 2. Берём данные за сегодня из бэкенда
                records = models.get_workouts_by_date_from_db(self.current_search_date)

                report = "=== ПОСЛЕДНЯЯ ТРЕНИРОВКА ===\n\n"

                if not records:
                    report += "В базе данных пока нет записей за сегодня."
                    self.msg_label.config(text=report, fg="#E53935")
                    if hasattr(self, 'btn_edit_hub'):
                        self.btn_edit_hub.destroy()
                    return

                # Наращиваем строки упражнений для текстового рапорта (БЕЗ КНОПОК!)
                for row in records:
                    ex_name = row[2]
                    sets = row[3]
                    reps = row[4]
                    weight = row[5]
                    weight_info = f" ({weight} кг)" if weight else ""
                    report += f"• {ex_name}: {sets}x{reps}{weight_info}\n"

                # Выводим чистый текст на экран
                self.msg_label.config(text=report, fg="#1565C0")

                # 3. Создаем ВСЕГО ОДНУ стильную графитовую кнопку под отчетом
                if hasattr(self, 'btn_edit_hub') and self.btn_edit_hub.winfo_exists():
                    self.btn_edit_hub.destroy()

                self.btn_edit_hub = tk.Button(
                    self.left_frame,
                    text="✏️ Управление записями дневника",
                    bg="#37474F", fg="white", font=("Arial", 11, "bold"),
                    command=self.open_edit_hub_window
                )
                self.btn_edit_hub.pack(pady=15, fill="x")

            except Exception as e:
                messagebox.showerror("Ошибка интерфейса", f"Не удалось обновить экран: {e}")

    def open_search_window(self):
        """Метод для вызова всплывающего интерактивного календаря и поиска по архиву."""
        # 1. Создаем красивое всплывающее Toplevel-окно для календаря
        cal_win = tk.Toplevel(self)
        cal_win.title("Выбор даты поиска")
        cal_win.geometry("320x340")
        cal_win.configure(bg="#0f172a")  # Наш фирменный благородный темно-синий фон
        cal_win.attributes("-topmost", True)
        cal_win.grab_set()

        lang_pack = LANGUAGES[self.current_lang]

        # 2. Разворачиваем визуальный кубик календаря
        # Передаем дату сессии, чтобы календарь сразу открывался на текущем дне
        now = datetime.datetime.now()
        cal = Calendar(
            cal_win,
            selectmode="day",
            date_pattern="dd-mm-yyyy",  # Наш железный формат дат для SQLite
            year=now.year,
            month=now.month,
            day=now.day
        )
        cal.pack(padx=15, pady=15, fill="both", expand=True)

        def confirm_date(event=None):
            """Считывает клик по дате, закрывает календарь и запускает поиск"""
            selected_date = cal.get_date()

            # Железно фиксируем дату архивного поиска в сессию в один клик
            self.current_search_date = selected_date

            # Перерисовываем благородную графитовую кнопку под этот день
            if hasattr(self, 'btn_edit_hub') and self.btn_edit_hub.winfo_exists():
                self.btn_edit_hub.destroy()

            self.btn_edit_hub = tk.Button(
                self.left_frame,
                text="✏️ Управление записями дневника",
                bg="#37474F", fg="white", font=("Arial", 11, "bold"),
                command=self.open_edit_hub_window
            )
            self.btn_edit_hub.pack(pady=15, fill="x")
            self.update_idletasks()

            cal_win.grab_release()
            cal_win.destroy()  # Закрываем календарь

            # Запускаем штатный поиск по базе SQLite
            try:
                rows = models.get_workouts_by_date_from_db(selected_date)

                # Интеллектуальный фронтенд для пустого дня
                if not rows:
                    msg = f"🔍 По запросу '{selected_date}' ничего не найдено.\nВы можете нажать 'Управление записями', чтобы добавить новую тренировку на этот день!"
                    self.msg_label.config(text=msg, fg="#E53935")
                    messagebox.showinfo(lang_pack["info_title"], msg)
                    return

                report = f"=== РЕЗУЛЬТАТЫ ПОИСКА ДЛЯ: {selected_date} ===\n"
                for row in rows:
                    _, date_str, ex, sets, reps, weight = row
                    report += f"📅 {date_str} | {ex} | {sets}x{reps}"
                    if weight is not None and weight != "":
                        report += f" ({weight} кг)\n"
                    else:
                        report += "\n"

                self.msg_label.config(text=report, fg="#1565C0")
                messagebox.showinfo(lang_pack["search_results_title"], report)

            except Exception as e:
                messagebox.showerror(lang_pack["error_search_title"], f"{lang_pack['error_search_msg']}{e}")

        # 3. Кнопка подтверждения выбора
        btn_text = "Выбрать дату" if self.current_lang == "ru" else "Select Date"
        tk.Button(
            cal_win, text=btn_text, font=("Arial", 11, "bold"),
            bg="#0284c7", fg="white", command=confirm_date
        ).pack(pady=(0, 15))

        # Горячая клавиша Enter (Return) для мгновенного выбора
        cal_win.bind("<Return>", confirm_date)

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

    def open_record_window(self, edit_record_id=None, old_ex="", old_sets="", old_reps="", old_weight="",
                           target_date=None):
        win = tk.Toplevel(self)
        win.configure(bg="#0f172a")  # 🔵 Премиальный глубокий темно-синий фон окна ввода

        # Интеллектуальный заголовок окна
        if edit_record_id:
            win.title("Редактировать запись")
        elif target_date:
            win.title(f"Новая запись на [{target_date}]")
        else:
            win.title("Новая тренировка")

        win.geometry("450x420")  # Увеличили высоту для статус-лейбла

        # Стилизация меток под синюю тему
        lbl_style = {"bg": "#0f172a", "fg": "#ffffff", "font": ("Arial", 10, "bold")}

        tk.Label(win, text="Упражнение:", **lbl_style).pack(pady=(10, 0))
        e_ex = ttk.Combobox(win, width=40, font=("Arial", 10))
        e_ex.pack(pady=5)
        e_ex.insert(0, old_ex)

        def on_dropdown_click():
            typed = e_ex.get().strip()
            if not typed:
                e_ex.configure(values=self.all_exercises)
            else:
                filtered = [ex for ex in self.all_exercises if typed.lower() in ex.lower()]
                e_ex.configure(values=filtered)

        e_ex.config(postcommand=on_dropdown_click)

        tk.Label(win, text="Подходы (число):", **lbl_style).pack()
        e_sets = tk.Entry(win, width=20, font=("Arial", 10))
        e_sets.pack(pady=5)
        e_sets.insert(0, str(old_sets))

        tk.Label(win, text="Повторения (число):", **lbl_style).pack()
        e_reps = tk.Entry(win, width=20, font=("Arial", 10))
        e_reps.pack(pady=5)
        e_reps.insert(0, str(old_reps))

        tk.Label(win, text="Вес (кг):", **lbl_style).pack()
        e_weight = tk.Entry(win, width=20, font=("Arial", 10))
        e_weight.pack(pady=5)
        e_weight.insert(0, str(old_weight) if old_weight is not None else "")

        # 1. СТРАТЕГИЧЕСКИЙ УЗЕЛ: Когнитивный статус-лейбл на синем фоне
        status_lbl = tk.Label(win, text="", font=("Arial", 10, "italic"), bg="#0f172a", wraplength=400)
        status_lbl.pack(pady=5)

        def save_and_close(event=None):  # Добавили event=None, чтобы метод корректно работал и от клика, и от Enter
            raw_ex = e_ex.get().strip()
            raw_sets = e_sets.get().strip()
            raw_reps = e_reps.get().strip()
            raw_weight = e_weight.get().strip().replace(",", ".")

            # Мягкая проверка на пустоту перед валидацией
            if not raw_ex or not raw_sets or not raw_reps:
                status_lbl.config(text="❌ Заполните упражнение, подходы и повторения!", fg="#E53935")
                return

            try:
                int(raw_sets)
                int(raw_reps)
                if raw_weight:
                    float(raw_weight)
            except ValueError:
                status_lbl.config(
                    text="❌ Внимание! Вес, подходы и повторения должны быть строго числами.",
                    fg="#E53935"
                )
                return

            # Вычисляем активную дату: приоритет у target_date, затем у глобальной сессии
            active_date = target_date if target_date else self.current_search_date

            success, result = models.validate_workout_data(raw_ex, raw_sets, raw_reps, raw_weight,
                                                           custom_date=active_date)
            if not success:
                status_lbl.config(text=f"⚠️ {result}", fg="#FF9800")
                return

            try:
                if edit_record_id:
                    db_weight = float(raw_weight) if raw_weight else None
                    db_success = models.update_workout_in_db(
                        edit_record_id, result.exercise_name, result.sets, result.reps, db_weight
                    )
                    if db_success:
                        messagebox.showinfo("Готово", "Запись успешно обновлена в базе данных!", parent=win)
                        self.all_exercises = models.get_unique_exercises()
                        win.destroy()  # При редактировании старой записи окно закрывать логично
                    else:
                        raise Exception("Ошибка выполнения SQL UPDATE")
                else:
                    # ПОТОКОВЫЙ ВВОД ДЛЯ НОВЫХ ЗАПИСЕЙ
                    models.save_workout_to_db(result)

                    # 💎 ЖЕЛЕЗНЫЙ ФИКС ВРЕМЕНИ: Берем чистую active_date без всяких опасных срезов строк!
                    status_lbl.config(text=f"💪 '{result.exercise_name}' успешно сохранено на {active_date}!",
                                      fg="#38bdf8")

                    # Мгновенная очистка полей для следующего упражнения
                    e_ex.set("")
                    e_sets.delete(0, tk.END)
                    e_reps.delete(0, tk.END)
                    e_weight.delete(0, tk.END)

                    # Обновляем список уникальных упражнений в памяти
                    self.all_exercises = models.get_unique_exercises()

                    # Автоматически возвращаем фокус на поле выбора упражнения
                    e_ex.focus()

            except Exception as e:
                status_lbl.config(text=f"❌ Не удалось сохранить: {e}", fg="#E53935")

        # 2. ШЛЮЗ ГОРЯЧИХ КЛАВИШ: Привязываем Enter (Return) ко всему окну Toplevel
        win.bind("<Return>", save_and_close)

        btn_text = "Обновить запись" if edit_record_id else "Сохранить (Enter)"
        btn_save = tk.Button(win, text=btn_text, bg="#0284c7", fg="white",  # Насыщенная синяя кнопка
                             font=("Arial", 12, "bold"), command=save_and_close)
        btn_save.pack(pady=10)

    def open_edit_hub_window(self):
        """Абсолютно универсальный интерактивный диспетчер Treeview с кнопками Редактирования и Добавления"""
        records = models.get_workouts_by_date_from_db(self.current_search_date)

        # ЗАЩИТА КОГНИТИВНОГО ТЕРПЕНИЯ: если день пустой, шлем сразу на форму добавления в прошлое!
        if not records:
            self.open_record_window(target_date=self.current_search_date)
            return

        # Если записи есть, разворачиваем наш любимый диспетчер
        hub_win = tk.Toplevel(self)
        hub_win.title("Управление записями")
        hub_win.geometry("550x400")  # Слегка увеличили высоту для двух кнопок
        hub_win.configure(bg="#FAFAFA")
        hub_win.attributes("-topmost", True)

        tk.Label(
            hub_win, text=f"Записи в архиве по запросу '{self.current_search_date}':",
            font=("Arial", 11, "bold"), bg="#FAFAFA", fg="#212121"
        ).pack(pady=10)

        columns = ("id", "date", "exercise", "sets", "reps", "weight")
        tree = ttk.Treeview(hub_win, columns=columns, show="headings", height=8)

        tree.heading("id", text="ID")
        tree.heading("date", text="Дата")
        tree.heading("exercise", text="Упражнение")
        tree.heading("sets", text="Подходы")
        tree.heading("reps", text="Повторения")
        tree.heading("weight", text="Вес (кг)")

        tree.column("id", width=40, anchor="center")
        tree.column("date", width=80, anchor="center")
        tree.column("exercise", width=150, anchor="w")
        tree.column("sets", width=60, anchor="center")
        tree.column("reps", width=80, anchor="center")
        tree.column("weight", width=70, anchor="center")

        tree.pack(padx=15, pady=5, fill="both", expand=True)

        for row in records:
            db_date = row[1]  # Берем полную дату без срезов
            rec_weight = f"{row[5]}" if row[5] is not None else "—"
            tree.insert("", "end", values=(row[0], db_date, row[2], row[3], row[4], rec_weight))

        # Панель управления (фрейм для красивого размещения двух кнопок в ряд)
        btn_frame = tk.Frame(hub_win, bg="#FAFAFA")
        btn_frame.pack(pady=15)

        def pre_open_edit():
            selected_item = tree.selection()
            if not selected_item:
                messagebox.showwarning("Внимание", "Пожалуйста, выберите строчку из таблицы!", parent=hub_win)
                return

            item_values = tree.item(selected_item, "values")
            r_id = int(item_values[0])
            ex = item_values[2]
            s = item_values[3]
            r = item_values[4]
            w = item_values[5] if item_values[5] != "—" else ""

            hub_win.destroy()
            self.open_record_window(edit_record_id=r_id, old_ex=ex, old_sets=s, old_reps=r, old_weight=w)

        def add_record_here():
            """Открывает окно ввода, жестко передавая текущую дату архивного дня"""
            hub_win.destroy()
            self.open_record_window(target_date=self.current_search_date)

        # Кнопка 1: Редактировать выбранное
        btn_select = tk.Button(
            btn_frame, text="✏️ Редактировать запись",
            font=("Arial", 11, "bold"), bg="#4CAF50", fg="white",
            command=pre_open_edit
        )
        btn_select.pack(side="left", padx=10)

        # Кнопка 2: Добавить новое в этот же день (Твой продуктовый инсайт!)
        btn_add_inline = tk.Button(
            btn_frame, text="📝 Добавить в этот день",
            font=("Arial", 11, "bold"), bg="#0284c7", fg="white",  # Фирменная синяя кнопка
            command=add_record_here
        )
        btn_add_inline.pack(side="left", padx=10)

        tree.bind("<Double-1>", lambda event: pre_open_edit())










