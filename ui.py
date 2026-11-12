import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import models
from strings import LANGUAGES
from  auth_window import AuthWindow
from tkcalendar import Calendar
from settings_window import SettingsWindow
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
        self.all_exercises = get_unique_exercises(1)

        self.current_search_date = datetime.datetime.now().strftime("%d-%m-%Y")

        # 3. Вызываем стартовое окно авторизации сессии
        AuthWindow(self, self.start_main_session)

    def start_main_session(self, user_name, lang, user_id):  # Добавили user_id в аргументы
        """Callback-метод: принимает данные из шлюза авторизации и разворачивает интерфейс"""
        self.active_user = user_name
        self.current_lang = lang
        self.active_user_id = user_id  # Железно фиксируем ID в сессию

        # Теперь подгружаем уникальные упражнения конкретного пользователя из бэкенда
        self.all_exercises = get_unique_exercises(self.active_user_id)

        # ... далее ваш код отрисовки интерфейса идет без изменений ...

        # Подтягиваем нужный языковой пакет из strings.py
        lang_pack = LANGUAGES[self.current_lang]

        # Строим архитектурные слои интерфейса
        self.left_frame = tk.Frame(self)
        self.left_frame.pack(side="left", fill="both", expand=True, padx=20, pady=20)

        self.label_hello = tk.Label(self.left_frame, text=lang_pack["hello"], font=("Arial", 18), fg="black")
        self.label_hello.pack(pady=40)

        # Настраиваем премиальный стальной стиль для таблиц Treeview
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#2b2b2b", foreground="#ffffff", fieldbackground="#2b2b2b",
            rowheight=28, font=("Arial", 10)
        )
        style.configure(
            "Treeview.Heading",
            background="#37474F", foreground="#ffffff", font=("Arial", 10, "bold")
        )

        # Создаем визуальную таблицу вместо старой текстовой метки
        self.report_frame = tk.LabelFrame(self.left_frame, text="📊 Отчёт по тренировке", font=("Arial", 11, "bold"),
                                          fg="#1565C0")
        self.report_frame.pack(fill="both", expand=True, pady=10)

        columns = ("exercise", "sets", "reps", "weight")
        self.tree = ttk.Treeview(self.report_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("exercise", text="🏋️ Упражнение")
        self.tree.heading("sets", text="🔢 Подходы")
        self.tree.heading("reps", text="🔁 Повторы")
        self.tree.heading("weight", text="⚖️ Вес")

        self.tree.column("exercise", width=180, anchor=tk.W)
        self.tree.column("sets", width=70, anchor=tk.CENTER)
        self.tree.column("reps", width=70, anchor=tk.CENTER)
        self.tree.column("weight", width=90, anchor=tk.CENTER)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.sidebar = tk.Frame(self, width=180, bg="#f0f0f0")
        self.sidebar.pack(side="right", fill="y", padx=10, pady=10)

        # Прошиваем динамический текст кнопок из словаря strings.py
        self.make_sidebar_btn(lang_pack["btn_record"], "#4CAF50", "white", self.open_record_window, 10)
        self.make_sidebar_btn(lang_pack["btn_last_workout"], "#8E24AA", "white", self.show_today_workouts, 10)
        self.make_sidebar_btn(lang_pack["btn_search"], "#FF9800", "black", self.open_search_window, 10)
        self.make_sidebar_btn(lang_pack["btn_timer"], "#FFD700", "black", self.open_timer_window, 10)
        self.make_sidebar_btn(text=lang_pack["btn_records"], bg="#00ff00", fg="black",
                              command=lambda: open_max_records_window(self))
        # Интегрируем премиальную кнопку вызова Центра Настроек
        btn_settings_text = "⚙️ Настройки" if self.current_lang == "ru" else "⚙️ Settings"
        self.make_sidebar_btn(btn_settings_text, "#607D8B", "white", self.open_settings_hub_window, 10)

        # === ВОТ СЮДА ВШИВАЕМ ЦЕНТРИРОВАНИЕ ПЕРЕД ВЫВОДОМ ИЗ ФОНА ===
        # Твоя геометрия 750x650, берем её за основу
        self._center_window(750, 650)

        # Выводим главное окно из фона на передний план во всей красе!
        self.deiconify()

        # Интегрируем премиальный футер (Подпись автора и статус сессии)
        self.footer_label = tk.Label(
            self.left_frame,
            text=f"v1.0.0-alpha | 🛡️ Разработчик: Александр | Активный профиль: {self.active_user} (ID: {self.active_user_id})",
            font=("Arial", 9, "italic"), fg="#555555"
        )
        self.footer_label.pack(side="bottom", pady=5)

    def _center_window(self, width: int, height: int):
        """Вычисляет координаты и позиционирует окно строго по центру экрана."""
        self.update_idletasks()  # Обновляем размеры подсистемы
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        # Точный расчет координат
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)

        self.geometry(f"{width}x{height}+{x}+{y}")

    def open_settings_hub_window(self):
        """Вызывает модальное окно настроек"""
        SettingsWindow(self, self.apply_new_settings)

    def apply_new_settings(self, new_lang):
        """Callback: принимает новые настройки и полностью перерисовывает главный экран"""
        self.current_lang = new_lang

        # Полностью сносим старые фреймы
        if hasattr(self, 'left_frame'):
            self.left_frame.destroy()
        if hasattr(self, 'sidebar'):
            self.sidebar.destroy()

        # Каскадно перезапускаем сессию с сохранением текущего ID пользователя
        self.start_main_session(self.active_user, self.current_lang, self.active_user_id)

    def make_sidebar_btn(self, text, bg, fg, command, pady_val=10):
        btn = tk.Button(self.sidebar, text=text, bg=bg, fg=fg,
                        font=("Arial", 11, "bold"), command=command,
                        width=25, anchor="w")
        btn.pack(fill="x", pady=pady_val)
        return btn

    def populate_tree_table(self, rows):
        """Метод для бесшовного вывода строк в главную таблицу Treeview"""
        for row in self.tree.get_children():
            self.tree.delete(row)

        for row in rows:
            # Прецизионная распаковка кортежа бэкенда из 6 элементов
            _, _, ex, sets, reps, weight = row
            weight_str = f"{weight} кг" if weight else "—"
            self.tree.insert("", "end", values=(ex, sets, reps, weight_str))

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

    def show_today_workouts(self):
        try:
            # 1. Запрашиваем данные за самый последний активный день
            last_day_data = models.get_all_record_from_last_day(self.active_user_id)

            if last_day_data:
                # ХИРУРГИЧЕСКИЙ ФИКС: берем первую запись, поле даты [1] и отсекаем первые 10 символов
                self.current_search_date = last_day_data[0][1][:10]
            else:
                self.current_search_date = datetime.datetime.now().strftime("%d-%m-%Y")

            # 2. Берём данные из бэкенда с жесткой фильтрацией по нашему user_id
            records = models.get_workouts_by_date_from_db(self.current_search_date, self.active_user_id)

            if not records:
                for row in self.tree.get_children():
                    self.tree.delete(row)
                if hasattr(self, 'btn_edit_hub'):
                    self.btn_edit_hub.destroy()
                return

            # 3. Бесшовно выводим в нашу новую красивую таблицу Treeview!
            self.populate_tree_table(records)

        except Exception as e:
            messagebox.showerror("Ошибка интерфейса", f"Не удалось обновить экран: {e}")

    

    def open_search_window(self):
        """Двухпанельный Центр Аналитики архива"""
        search_win = tk.Toplevel(self)
        search_win.title("Центр Аналитики: Поиск по архиву")
        search_win.geometry("750x400")
        search_win.configure(bg="#0f172a")
        search_win.attributes("-topmost", True)
        search_win.grab_set()

        lang_pack = LANGUAGES[self.current_lang]

        # ЛЕВАЯ ПАНЕЛЬ: Календарь
        left_panel = tk.Frame(search_win, bg="#0f172a")
        left_panel.pack(side="left", fill="y", padx=15, pady=15)

        now = datetime.datetime.now()
        cal = Calendar(
            left_panel, selectmode="day", date_pattern="dd-mm-yyyy",
            year=now.year, month=now.month, day=now.day
        )
        cal.pack(padx=5, pady=5, fill="both", expand=True)

        # ПРАВАЯ ПАНЕЛЬ: Таблица результатов
        right_panel = tk.LabelFrame(search_win, text="📋 Результаты поиска", font=("Arial", 11, "bold"), bg="#1e293b",
                                    fg="#38bdf8")
        right_panel.pack(side="right", fill="both", expand=True, padx=15, pady=15)

        columns = ("exercise", "sets", "reps", "weight")
        search_tree = ttk.Treeview(right_panel, columns=columns, show="headings", selectmode="browse")
        search_tree.heading("exercise", text="🏋️ Упражнение")
        search_tree.heading("sets", text="🔢 Подходы")
        search_tree.heading("reps", text="🔁 Повторы")
        search_tree.heading("weight", text="⚖️ Вес")

        search_tree.column("exercise", width=180, anchor=tk.W)
        search_tree.column("sets", width=60, anchor=tk.CENTER)
        search_tree.column("reps", width=60, anchor=tk.CENTER)
        search_tree.column("weight", width=80, anchor=tk.CENTER)
        search_tree.pack(fill="both", expand=True, padx=10, pady=10)

        def confirm_date(event=None):
            selected_date = cal.get_date()
            self.current_search_date = selected_date

            if hasattr(self, 'btn_edit_hub') and self.btn_edit_hub.winfo_exists():
                self.btn_edit_hub.destroy()

            self.btn_edit_hub = tk.Button(
                self.left_frame, text="✏️ Управление записями дневника",
                bg="#37474F", fg="white", font=("Arial", 11, "bold"),
                command=self.open_edit_hub_window
            )
            self.btn_edit_hub.pack(pady=15, fill="x")
            self.update_idletasks()

            try:
                rows = models.get_workouts_by_date_from_db(selected_date, self.active_user_id)

                for row in search_tree.get_children():
                    search_tree.delete(row)

                if not rows:
                    messagebox.showinfo(lang_pack["info_title"], f"🔍 По запросу '{selected_date}' ничего не найдено.")
                    return

                for row in rows:
                    _, _, ex, sets, reps, weight = row
                    weight_str = f"{weight} кг" if weight else "—"
                    search_tree.insert("", "end", values=(ex, sets, reps, weight_str))

                # Дублируем вывод на главный экран
                self.populate_tree_table(rows)

            except Exception as e:
                messagebox.showerror(lang_pack["error_search_title"], f"{lang_pack['error_search_msg']}{e}")

        btn_text = "Выбрать дату" if self.current_lang == "ru" else "Select Date"
        tk.Button(left_panel, text=btn_text, font=("Arial", 11, "bold"), bg="#0284c7", fg="white",
                  command=confirm_date).pack(pady=10, fill="x")
        search_win.bind("<Return>", confirm_date)

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

        # 💎 ЛЮКСОВЫЙ ГЕНДЕРНЫЙ ИНСАЙТ : Автоматическая прошивка цветов сессии!
        # 💎 ОБНОВЛЕННАЯ ЛЮКСОВАЯ ПАЛИТРА СОФРИНА: Чистый розовый йогурт для девочки!
        if self.active_user == "Супруга":
            bg_main = "#fce7f3"  # Нежно-розовый пастельный фон (светлый, приятный глазу)
            fg_label = "#1e293b"  # Темно-графитовый текст меток для идеальной контрастности
            fg_accent = "#db2777"  # Насыщенный розовый цвет для когнитивного статуса
            bg_btn = "#ec4899"  # Яркая, красивая розовая кнопка сохранения
        else:
            bg_main = "#0f172a"  # Твой стальной глубокий синий фон
            fg_label = "#ffffff"
            fg_accent = "#38bdf8"  # Неоново-голубой акцент
            bg_btn = "#0284c7"  # Синяя кнопка

        win.configure(bg=bg_main)  # Накатываем выбранный фон на окно сессии

        # Интеллектуальный заголовок окна
        if edit_record_id:
            win.title("Редактировать запись")
        elif target_date:
            win.title(f"Новая запись на [{target_date}]")
        else:
            win.title("Новая тренировка")

        win.geometry("450x420")

        # Перепрошиваем стилизацию меток под динамические переменные
        lbl_style = {"bg": bg_main, "fg": fg_label, "font": ("Arial", 10, "bold")}

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

        status_lbl = tk.Label(win, text="", font=("Arial", 10, "italic"), bg=bg_main, wraplength=400)
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
            active_date = target_date if target_date else datetime.datetime.now().strftime("%d-%m-%Y")


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

                    # ПОТОКОВЫЙ ВВОД ДЛЯ НОВЫХ ЗАПИСЕЙ — передаем объект и наш active_user_id
                    models.save_workout_to_db(result, self.active_user_id)

                    # Железный фикс времени: берем чистую active_date
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
        btn_save = tk.Button(win, text=btn_text, bg=bg_btn, fg="white",
                             font=("Arial", 12, "bold"), command=save_and_close)
        btn_save.pack(pady=10)

    def open_edit_hub_window(self):
        """Абсолютно универсальный интерактивный диспетчер Treeview с кнопками Редактирования"""
        # Передаем дату и числовой ID пользователя в бэкенд
        records = models.get_workouts_by_date_from_db(self.current_search_date, self.active_user_id)

        # Защита когнитивного терпения: если день пустой, шлем сразу на форму добавления
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










