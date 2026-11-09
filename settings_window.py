import tkinter as tk
from tkinter import ttk
from strings import LANGUAGES


class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, on_save_callback):
        """
        ⚙️ Глобальный Центр Настроек (Settings Hub) Workout Vault.
        parent: главная инстанция WorkoutApp
        on_save_callback: функция в ui.py, которая применит изменения в реальном времени
        """
        super().__init__(parent)
        self.parent = parent
        self.on_save_callback = on_save_callback

        self.title("⚙️ Настройки системы / Settings")
        self.geometry("400x380")

        # Автоматический выбор цвета фона окна настроек на основе вожака сессии!
        if self.parent.active_user == "Супруга":
            self.bg_main = "#2e1520"  # Темно-розовый благородный фон для девочки
            self.fg_accent = "#f472b6"  # Нежно-розовый акцент
            self.bg_btn = "#db2777"  # Красивая розовая кнопка
        else:
            self.bg_main = "#0f172a"  # Твой благородный глубокий синий фон
            self.fg_accent = "#38bdf8"  # Неоново-голубой акцент
            self.bg_btn = "#0284c7"  # Синяя кнопка

        self.configure(bg=self.bg_main)

        # Делаем окно модальным (поверх всех, фокус на нем)
        self.attributes("-topmost", True)
        self.grab_set()

        # Разворачиваем графические слои интерфейса
        self.build_ui()

    def build_ui(self):
        # Очищаем старые виджеты для динамического обновления
        for widget in self.winfo_children():
            widget.destroy()

        lang_pack = LANGUAGES[self.parent.current_lang]

        # 1. Главный заголовок
        tk.Label(
            self, text=lang_pack["btn_edit_hub"].split(" ")[1] if " " in lang_pack["btn_edit_hub"] else "SETTINGS",
            font=("Arial", 16, "bold"), bg=self.bg_main, fg=self.fg_accent
        ).pack(pady=(20, 15))

        # Информационная плашка активной сессии
        user_info = f"👤 Активный профиль: {self.parent.active_user}" if self.parent.current_lang == "ru" else f"👤 Active profile: {self.parent.active_user}"
        tk.Label(
            self, text=user_info, font=("Arial", 11, "bold"),
            bg=self.bg_main, fg="#ffffff"
        ).pack(pady=5)

        # Разделительная линия
        canvas = tk.Canvas(self, height=2, bg="#bdbdbd", highlightthickness=0)
        canvas.pack(fill="x", padx=40, pady=15)

        # 2. Интерактивный блок переключения языков
        lang_label_text = "Смена языка сессии:" if self.parent.current_lang == "ru" else "Change session language:"
        tk.Label(
            self, text=lang_label_text, font=("Arial", 10, "bold"),
            bg=self.bg_main, fg="#ffffff"
        ).pack(pady=(5, 0))

        self.combo_lang = ttk.Combobox(self, values=["Русский (RU)", "English (EN)"], state="readonly", width=25)
        self.combo_lang.pack(pady=5)
        self.combo_lang.current(0 if self.parent.current_lang == "ru" else 1)
        self.combo_lang.bind("<<ComboboxSelected>>", self.preview_language)

        # 3. Фирменная кнопка сохранения настроек
        save_btn_text = "Применить" if self.parent.current_lang == "ru" else "Apply"
        self.btn_save = tk.Button(
            self, text=save_btn_text, font=("Arial", 11, "bold"),
            bg=self.bg_btn, fg="white", width=18, command=self.save_settings
        )
        self.btn_save.pack(pady=35)

        # Привязка клавиши Enter
        self.bind("<Return>", lambda event: self.save_settings())

    def preview_language(self, event):
        """Временно меняет язык внутри самого окна настроек для демонстрации"""
        selected = self.combo_lang.get()
        if "Русский" in selected:
            self.parent.current_lang = "ru"
        else:
            self.parent.current_lang = "en"
        self.build_ui()

    def save_settings(self):
        """Запечатывает выбранные настройки и передает их в главный контур фронтенда"""
        selected_lang = "ru" if "Русский" in self.combo_lang.get() else "en"

        # Швыряем сигнал обратно в ui.py через callback
        self.on_save_callback(selected_lang)

        self.grab_release()
        self.destroy()  # Бесшовное закрытие настроек
