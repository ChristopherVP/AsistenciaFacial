from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from PIL import ImageTk

from ..auth import User, UserRepository
from ..branding import make_logo
from ..config import (
    APP_TITLE,
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_CARD,
    COLOR_DANGER,
    COLOR_MUTED,
    COLOR_SELECT,
    COLOR_SUCCESS,
    COLOR_TEXT,
    FONT_FAMILY,
    SECURITY_QUESTIONS,
)
from ..errors import AppError
from ..validators import allows_cedula_input, allows_name_input, allows_username_input, normalize_username
from .window_utils import maximize

PASSWORD_MASK = "•"
FORM_WIDTH = 440
MAX_SAVED_CARDS = 4
GRADIENT_TOP = (11, 37, 64)
GRADIENT_BOTTOM = (27, 108, 168)
SAVED_BG = "#EAF2FB"
FEATURES = (
    "📷  Registro rápido con tu rostro",
    "✔  Listas de asistencia en Excel",
    "🔒  Acceso protegido con tu cuenta",
)


def _blend(start: tuple[int, int, int], end: tuple[int, int, int], ratio: float) -> str:
    red, green, blue = (round(a + (b - a) * ratio) for a, b in zip(start, end))
    return f"#{red:02x}{green:02x}{blue:02x}"


class BrandPanel(tk.Canvas):
    """Panel izquierdo: degradado azul con un visor de cámara y reconocimiento facial."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, highlightthickness=0, bg=_blend(GRADIENT_TOP, GRADIENT_BOTTOM, 0))
        self.bind("<Configure>", lambda _event: self._draw())

    def _draw(self) -> None:
        self.delete("all")
        width, height = self.winfo_width(), self.winfo_height()
        if width < 50 or height < 50:
            return
        self._gradient(width, height)
        radius = min(width * 0.26, height * 0.17)
        center_x, center_y = width / 2, height * 0.33
        self._lens(center_x, center_y, radius)
        self._viewfinder(center_x, center_y, radius)
        self._texts(width, center_y + radius * 1.75 - 20)

    def _gradient(self, width: int, height: int) -> None:
        step = 3
        for top in range(0, height, step):
            color = _blend(GRADIENT_TOP, GRADIENT_BOTTOM, top / height)
            self.create_rectangle(0, top, width, top + step, fill=color, outline=color)

    def _circle(self, x: float, y: float, radius: float, **options: object) -> None:
        self.create_oval(x - radius, y - radius, x + radius, y + radius, **options)

    def _lens(self, x: float, y: float, radius: float) -> None:
        self._circle(x, y, radius * 1.75, outline="#2A6AA0", width=1)
        self._circle(x, y, radius * 1.45, outline="#3A7DB5", width=1)
        self._circle(x, y, radius * 1.1, fill="#0E2C4A", outline="#4A90C8", width=3)
        self._circle(x, y, radius * 0.82, fill="#1F4E79", outline="#2E86C1", width=2)
        self._circle(x, y, radius * 0.55, fill="#2E86C1")
        self._circle(x, y, radius * 0.34, fill="#0B2038")
        self._circle(x - radius * 0.14, y - radius * 0.14, radius * 0.09, fill="#CFE8FA", outline="")

    def _viewfinder(self, x: float, y: float, radius: float) -> None:
        half, arm = radius * 1.35, radius * 0.38
        for sign_x in (-1, 1):
            for sign_y in (-1, 1):
                corner_x, corner_y = x + sign_x * half, y + sign_y * half
                self.create_line(
                    corner_x - sign_x * arm, corner_y, corner_x, corner_y, corner_x, corner_y - sign_y * arm,
                    fill="#7FD1F0", width=4, joinstyle="round", capstyle="round",
                )
        self.create_line(x - half, y, x + half, y, fill="#5BC0EB", dash=(6, 6))
        badge_x, badge_y, badge = x + half, y + half, radius * 0.3
        self._circle(badge_x, badge_y, badge, fill=COLOR_SUCCESS, outline="white", width=3)
        self.create_line(
            badge_x - badge * 0.45, badge_y, badge_x - badge * 0.1, badge_y + badge * 0.4,
            badge_x + badge * 0.5, badge_y - badge * 0.35,
            fill="white", width=4, capstyle="round", joinstyle="round",
        )

    def _texts(self, width: int, top: float) -> None:
        middle = width / 2
        self.create_text(
            middle, top + 55, text=APP_TITLE, fill="white", font=(FONT_FAMILY, 28, "bold")
        )
        self.create_text(
            middle, top + 95, text="Control de asistencia con reconocimiento facial",
            fill="#BFE0F5", font=(FONT_FAMILY, 12),
        )
        for index, feature in enumerate(FEATURES):
            self.create_text(
                middle, top + 160 + index * 34, text=feature, fill="#E3F2FC", font=(FONT_FAMILY, 12)
            )


class LoginWindow:
    """Ventana de acceso a pantalla completa. `run()` devuelve el usuario o None."""

    def __init__(self, root: tk.Tk, users: UserRepository, icon: ImageTk.PhotoImage) -> None:
        self._users = users
        self._result: User | None = None
        self._submit: Callable[[], None] = lambda: None
        self._password_entries: list[ttk.Entry] = []
        self._window = tk.Toplevel(root)
        self._window.title(f"{APP_TITLE} — Acceso")
        self._window.configure(bg=COLOR_CARD)
        self._window.minsize(960, 700)
        self._window.iconphoto(True, icon)
        self._window.protocol("WM_DELETE_WINDOW", self._window.destroy)
        self._window.bind("<Return>", lambda _event: self._submit())
        self._show_password = tk.BooleanVar(value=False)
        self._error_var = tk.StringVar()
        self._cedula_check = (self._window.register(allows_cedula_input), "%P")
        self._name_check = (self._window.register(allows_name_input), "%P")
        self._user_check = (self._window.register(allows_username_input), "%P")
        self._build_layout()
        maximize(self._window)
        if users.has_users:
            self._show_login()
        else:
            self._show_register(first_user=True)

    def run(self) -> User | None:
        self._window.lift()
        self._window.focus_force()
        self._window.wait_window()
        return self._result

    def _build_layout(self) -> None:
        self._window.grid_rowconfigure(0, weight=1)
        self._window.grid_columnconfigure(0, weight=44, uniform="columns")
        self._window.grid_columnconfigure(1, weight=56, uniform="columns")
        BrandPanel(self._window).grid(row=0, column=0, sticky="nsew")
        right = tk.Frame(self._window, bg=COLOR_CARD)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)
        self._content = tk.Frame(right, bg=COLOR_CARD)
        self._content.grid(row=0, column=0)

    # ---------- piezas reutilizables ----------

    def _reset_view(self, title: str, hint: str) -> tk.Frame:
        for child in self._content.winfo_children():
            child.destroy()
        self._password_entries = []
        self._error_var.set("")
        tk.Frame(self._content, width=FORM_WIDTH, height=1, bg=COLOR_CARD).pack()
        ttk.Label(
            self._content, text=title, style="Card.TLabel", font=(FONT_FAMILY, 26, "bold")
        ).pack(anchor="w")
        ttk.Label(
            self._content, text=hint, style="Hint.TLabel", wraplength=FORM_WIDTH, font=(FONT_FAMILY, 11)
        ).pack(anchor="w", pady=(2, 14))
        return self._content

    def _field(
        self,
        parent: tk.Misc,
        caption: str,
        variable: tk.StringVar,
        check: tuple[str, str] | None = None,
        secret: bool = False,
    ) -> ttk.Entry:
        ttk.Label(parent, text=caption, style="Card.TLabel", font=(FONT_FAMILY, 10, "bold")).pack(
            anchor="w", pady=(10, 3)
        )
        options: dict[str, object] = {"textvariable": variable, "font": (FONT_FAMILY, 11)}
        if check is not None:
            options.update(validate="key", validatecommand=check)
        if secret:
            options["show"] = "" if self._show_password.get() else PASSWORD_MASK
        entry = ttk.Entry(parent, **options)
        entry.pack(fill="x")
        if secret:
            self._password_entries.append(entry)
        return entry

    def _pair(self, parent: tk.Misc) -> tuple[tk.Frame, tk.Frame]:
        row = tk.Frame(parent, bg=COLOR_CARD)
        row.pack(fill="x")
        left, right = tk.Frame(row, bg=COLOR_CARD), tk.Frame(row, bg=COLOR_CARD)
        left.pack(side="left", fill="x", expand=True, padx=(0, 8))
        right.pack(side="left", fill="x", expand=True, padx=(8, 0))
        return left, right

    def _show_password_toggle(self, parent: tk.Misc) -> None:
        ttk.Checkbutton(
            parent,
            text="👁  Mostrar contraseña",
            variable=self._show_password,
            command=self._apply_password_visibility,
            style="Card.TCheckbutton",
        ).pack(anchor="w", pady=(10, 0))

    def _apply_password_visibility(self) -> None:
        mask = "" if self._show_password.get() else PASSWORD_MASK
        for entry in self._password_entries:
            entry.configure(show=mask)

    def _error_label(self, parent: tk.Misc) -> None:
        ttk.Label(
            parent, textvariable=self._error_var, style="Error.TLabel", wraplength=FORM_WIDTH, justify="left"
        ).pack(anchor="w", pady=(10, 0))

    def _button(self, parent: tk.Misc, text: str, style: str, command: Callable[[], None]) -> None:
        ttk.Button(parent, text=text, style=style, command=command).pack(fill="x", pady=(14, 0), ipady=4)

    def _link(self, parent: tk.Misc, text: str, command: Callable[[], None]) -> tk.Label:
        link = tk.Label(
            parent, text=text, bg=COLOR_CARD, fg=COLOR_ACCENT, cursor="hand2",
            font=(FONT_FAMILY, 10, "underline"),
        )
        link.bind("<Button-1>", lambda _event: command())
        return link

    def _fail(self, error: Exception) -> None:
        self._error_var.set(str(error))

    def _finish(self, user: User) -> None:
        self._result = user
        self._window.destroy()

    # ---------- vista: iniciar sesión ----------

    def _show_login(self, username: str = "", notice: str = "") -> None:
        body = self._reset_view("Iniciar sesión", notice or "Ingresa con tu usuario y contraseña.")
        saved = self._users.remembered_users()[:MAX_SAVED_CARDS]
        if saved:
            ttk.Label(
                body, text="Entrar con un clic", style="Card.TLabel", font=(FONT_FAMILY, 10, "bold")
            ).pack(anchor="w")
            for user in saved:
                self._saved_user_card(body, user)
            ttk.Separator(body).pack(fill="x", pady=(14, 2))
        user_var, password_var = tk.StringVar(value=username), tk.StringVar()
        user_entry = self._field(body, "Usuario", user_var, self._user_check)
        password_entry = self._field(body, "Contraseña", password_var, secret=True)
        self._show_password_toggle(body)
        self._error_label(body)
        self._submit = lambda: self._login(user_var.get(), password_var.get())
        self._button(body, "Ingresar", "Primary.TButton", self._submit)
        self._link(
            body, "¿Olvidaste tu contraseña?", lambda: self._show_recover(user_var.get())
        ).pack(anchor="w", pady=(16, 0))
        self._link(body, "¿No tienes cuenta? Regístrate aquí", self._show_register).pack(
            anchor="w", pady=(6, 0)
        )
        (password_entry if username else user_entry).focus_set()

    def _saved_user_card(self, parent: tk.Misc, user: User) -> None:
        card = tk.Frame(
            parent, bg=SAVED_BG, highlightthickness=1, highlightbackground=COLOR_BORDER, cursor="hand2"
        )
        card.pack(fill="x", pady=(6, 0))
        name = tk.Label(
            card, text=f"👤  {user.full_name}", bg=SAVED_BG, fg=COLOR_TEXT,
            font=(FONT_FAMILY, 11, "bold"), anchor="w", cursor="hand2",
        )
        name.pack(fill="x", padx=12, pady=(8, 0))
        detail = tk.Label(
            card, text=f"@{user.username}  ·  clic para entrar", bg=SAVED_BG, fg=COLOR_MUTED,
            font=(FONT_FAMILY, 9), anchor="w", cursor="hand2",
        )
        detail.pack(fill="x", padx=12, pady=(0, 8))
        widgets = (card, name, detail)
        for widget in widgets:
            widget.bind("<Button-1>", lambda _event, item=user: self._enter_saved(item))
            widget.bind("<Enter>", lambda _event: [w.configure(bg=COLOR_SELECT) for w in widgets])
            widget.bind("<Leave>", lambda _event: [w.configure(bg=SAVED_BG) for w in widgets])

    def _enter_saved(self, user: User) -> None:
        try:
            self._finish(self._users.authenticate_remembered(user.cedula))
        except AppError as error:
            self._show_login(notice=str(error))

    def _login(self, username: str, password: str) -> None:
        if not username.strip() or not password:
            self._error_var.set("Escribe tu usuario y tu contraseña.")
            return
        try:
            user = self._users.authenticate(username, password)
        except AppError as error:
            self._fail(error)
            return
        self._finish(self._offer_to_remember(user))

    def _offer_to_remember(self, user: User) -> User:
        if user.remembered:
            return user
        wants_it = messagebox.askyesno(
            "¿Guardar usuario?",
            "¿Desea guardar este usuario para entrar con un solo clic la próxima vez?\n\n"
            "Podrá desactivarlo cuando quiera en Ajustes → Mi cuenta.",
            parent=self._window,
        )
        if not wants_it:
            return user
        try:
            return self._users.set_remembered(user.cedula, True)
        except AppError as error:
            messagebox.showwarning(APP_TITLE, f"No se pudo guardar el usuario: {error}", parent=self._window)
            return user

    # ---------- vista: crear cuenta ----------

    def _username_status(self, text: str) -> tuple[str, str]:
        if not text:
            return "", COLOR_MUTED
        try:
            name = normalize_username(text)
        except AppError as error:
            return str(error), COLOR_MUTED
        if self._users.username_taken(name):
            return f"✖  «{name}» ya está en uso", COLOR_DANGER
        return f"✔  «{name}» está disponible", COLOR_SUCCESS

    def _show_register(self, first_user: bool = False) -> None:
        hint = "Crea el primer usuario del sistema." if first_user else "Cada cédula y cada usuario son únicos."
        body = self._reset_view("Crear cuenta", hint)
        cedula_var, name_var, user_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        password_var, confirm_var = tk.StringVar(), tk.StringVar()
        question_var, answer_var = tk.StringVar(value=SECURITY_QUESTIONS[0]), tk.StringVar()
        left, right = self._pair(body)
        cedula_entry = self._field(left, "Cédula", cedula_var, self._cedula_check)
        self._field(right, "Usuario", user_var, self._user_check)
        status = tk.Label(body, bg=COLOR_CARD, fg=COLOR_MUTED, font=(FONT_FAMILY, 9), anchor="w", wraplength=FORM_WIDTH, justify="left")
        status.pack(fill="x", pady=(4, 0))
        user_var.trace_add(
            "write",
            lambda *_args: status.configure(
                **dict(zip(("text", "fg"), self._username_status(user_var.get())))
            ),
        )
        self._field(body, "Apellidos y nombres", name_var, self._name_check)
        left, right = self._pair(body)
        self._field(left, "Contraseña (mín. 8)", password_var, secret=True)
        self._field(right, "Repetir contraseña", confirm_var, secret=True)
        self._show_password_toggle(body)
        ttk.Label(
            body, text="Pregunta de seguridad (para recuperar la cuenta)", style="Card.TLabel",
            font=(FONT_FAMILY, 10, "bold"),
        ).pack(anchor="w", pady=(10, 3))
        ttk.Combobox(
            body, textvariable=question_var, values=SECURITY_QUESTIONS, state="readonly",
            font=(FONT_FAMILY, 11),
        ).pack(fill="x")
        self._field(body, "Respuesta", answer_var)
        self._error_label(body)

        def submit() -> None:
            try:
                user = self._users.register(
                    cedula_var.get(), name_var.get(), user_var.get(), password_var.get(),
                    confirm_var.get(), question_var.get(), answer_var.get(),
                )
            except AppError as error:
                self._fail(error)
                return
            self._show_login(user.username, "✔ Cuenta creada. Ahora inicia sesión.")

        self._submit = submit
        self._button(body, "Crear cuenta", "Success.TButton", submit)
        if self._users.has_users:
            self._link(body, "← Volver a iniciar sesión", self._show_login).pack(anchor="w", pady=(14, 0))
        cedula_entry.focus_set()

    # ---------- vista: recuperar contraseña ----------

    def _show_recover(self, username: str = "") -> None:
        body = self._reset_view(
            "Recuperar contraseña", "Escribe tu usuario para ver tu pregunta de seguridad."
        )
        user_var = tk.StringVar(value=username)
        entry = self._field(body, "Usuario", user_var, self._user_check)
        self._error_label(body)

        def search() -> None:
            try:
                question = self._users.security_question(user_var.get())
            except AppError as error:
                self._fail(error)
                return
            self._show_reset_form(user_var.get().strip().lower(), question)

        self._submit = search
        self._button(body, "Continuar", "Primary.TButton", search)
        self._link(body, "← Volver a iniciar sesión", self._show_login).pack(anchor="w", pady=(14, 0))
        entry.focus_set()

    def _show_reset_form(self, username: str, question: str) -> None:
        body = self._reset_view("Nueva contraseña", f"Usuario @{username}")
        answer_var, password_var, confirm_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        answer_entry = self._field(body, question, answer_var)
        self._field(body, "Nueva contraseña (mínimo 8 caracteres)", password_var, secret=True)
        self._field(body, "Repetir nueva contraseña", confirm_var, secret=True)
        self._show_password_toggle(body)
        self._error_label(body)

        def submit() -> None:
            try:
                user = self._users.recover_password(
                    username, answer_var.get(), password_var.get(), confirm_var.get()
                )
            except AppError as error:
                self._fail(error)
                return
            self._show_login(user.username, "✔ Contraseña actualizada. Inicia sesión.")

        self._submit = submit
        self._button(body, "Cambiar contraseña", "Success.TButton", submit)
        self._link(body, "← Volver a iniciar sesión", self._show_login).pack(anchor="w", pady=(14, 0))
        answer_entry.focus_set()
