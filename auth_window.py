import tkinter as tk
from tkinter import ttk
from strings import LANGUAGES


class AuthWindow(tk.Toplevel):
    def __init__(self, parent, on_success_callback):
        """
        Стартовый шлюз авторизации сессии (Welcome / Login Screen).
        parent: главная инстанция WorkoutApp (пока скрытая в фоне)
        on_success_callback: функция, которая примет параметры и развернет главный экран
        """
        super().__init__(parent)
        self.parent = parent
        self.on_success_callback = on_success_callback

        self.title("Шлюз авторизации / Welcome")
        self.geometry("400x320")
        self.configure(bg="#0f172a")  # Благородный глубокий синий фон

        # Фиксируем, что окно поверх всех и фокус строго на нем
        self.attributes("-topmost", True)
        self.grab_set()

        # Локальная переменная языка стартового окна (по умолчанию "ru")
        self.current_lang = "ru"

        # Перехватываем закрытие окна на крестик, чтобы корректно тушить все приложение
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Разворачиваем графические элементы
        self.build_ui()

    def build_ui(self):
        # Очищаем старые элементы, если меняется язык на лету
        for widget in self.winfo_children():
            widget.destroy()

        lang_pack = LANGUAGES[self.current_lang]

        # 1. Заголовок
        self.lbl_welcome = tk.Label(
            self, text="WORKOUT VAULT",
            font=("Arial", 16, "bold"), bg="#0f172a", fg="#38bdf8"
        )
        self.lbl_welcome.pack(pady=(20, 10))

        # 2. Блок выбора языка (i18n)
        tk.Label(
            self, text="Выбор языка / Select Language:",
            font=("Arial", 10, "bold"), bg="#0f172a", fg="#ffffff"
        ).pack(pady=(10, 0))

        self.combo_lang = ttk.Combobox(self, values=["Русский (RU)", "English (EN)"], state="readonly", width=25)
        self.combo_lang.pack(pady=5)
        # Устанавливаем текущее выбранное значение
        self.combo_lang.current(0 if self.current_lang == "ru" else 1)
        self.combo_lang.bind("<<ComboboxSelected>>", self.change_language)

        # 3. Блок выбора профиля (Аккаунтность)
        tk.Label(
            self, text="Аккаунт / Profile:",
            font=("Arial", 10, "bold"), bg="#0f172a", fg="#ffffff"
        ).pack(pady=(10, 0))

        # Передаем имена наших вожаков сессии
        self.combo_user = ttk.Combobox(self, values=["Александр", "Супруга"], state="readonly", width=25)
        self.combo_user.pack(pady=5)
        self.combo_user.current(0)

        # 4. Премиальная кнопка авторизации (В БОЙ! 🦾)
        btn_text = "В БОЙ! 💪" if self.current_lang == "ru" else "GO! 💪"
        self.btn_login = tk.Button(
            self, text=btn_text, font=("Arial", 12, "bold"),
            bg="#0284c7", fg="white", width=15, command=self.login_success
        )
        self.btn_login.pack(pady=25)

        # Горячая клавиша Enter на кнопку
        self.bind("<Return>", lambda event: self.login_success())

    def change_language(self, event):
        """Мгновенно перепрошивает надписи в стартовом окне при выборе языка"""
        selected = self.combo_lang.get()
        if "Русский" in selected:
            self.current_lang = "ru"
        else:
            self.current_lang = "en"
        self.build_ui()  # Каскадная перерисовка интерфейса стартового окна

    def login_success(self):
        """Считывает параметры сессии и швыряет их в главный контур программы"""
        user_name = self.combo_user.get()
        # Вызываем callback-функцию в главном ui.py и передаем туда данные
        self.on_success_callback(user_name, self.current_lang)
        self.grab_release()
        self.destroy()  # Бесшовное уничтожение стартового шлюза

    def on_close(self):
        """Если закрыли на крестик — полностью закрываем весь процесс"""
        self.grab_release()
        self.parent.destroy()
