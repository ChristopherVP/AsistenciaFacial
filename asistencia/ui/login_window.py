from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from PIL import ImageTk

from ..auth import User, UserRepository
from ..branding import make_logo
from ..config import (
    APP_TITLE,
    COLOR_BG,
    COLOR_BORDER,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_SELECT,
    COLOR_TEXT,
    FONT_FAMILY,
    SECURITY_QUESTIONS,
)
from ..errors import AppError
from ..validators import allows_cedula_input, allows_name_input
from .widgets import Card

WINDOW_WIDTH = 470
PASSWORD_MASK = "•"


class LoginWindow:
    """Ventana modal de acceso. `run()` devuelve el usuario autenticado o None."""

    def __init__(self, root: tk.Tk, users: UserRepository, icon: ImageTk.PhotoImage) -> None:
        self._users = users
        self._result: User | None = None
        self._submit: Callable[[], None] = lambda: None
        self._password_entries: list[ttk.Entry] = []
        self._window = tk.Toplevel(root)
        self._window.title(f"{APP_TITLE} — Acceso")
        self._window.configure(bg=COLOR_BG)
        self._window.resizable(False, False)
        self._window.iconphoto(True, icon)
        self._window.protocol("WM_DELETE_WINDOW", self._window.destroy)
        self._window.bind("<Return>", lambda _event: self._submit())
        self._logo = ImageTk.PhotoImage(make_logo(54))
        self._show_password = tk.BooleanVar(value=False)
        self._error_var = tk.StringVar()
        self._cedula_check = (self._window.register(allows_cedula_input), "%P")
        self._name_check = (self._window.register(allows_name_input), "%P")
        self._build_header()
        self._content = tk.Frame(self._window, bg=COLOR_BG)
        self._content.pack(fill="both", expand=True, padx=18, pady=(14, 18))
        if users.has_users:
            self._show_login()
        else:
            self._show_register(first_user=True)

    def run(self) -> User | None:
        self._center()
        self._window.lift()
        self._window.focus_force()
        self._window.wait_window()
        return self._result

    def _center(self) -> None:
        self._window.update_idletasks()
        width = max(WINDOW_WIDTH, self._window.winfo_reqwidth())
        height = self._window.winfo_reqheight()
        x = (self._window.winfo_screenwidth() - width) // 2
        y = max(10, (self._window.winfo_screenheight() - height) // 3)
        self._window.geometry(f"{width}x{height}+{x}+{y}")

    def _build_header(self) -> None:
        header = tk.Frame(self._window, bg=COLOR_PRIMARY)
        header.pack(fill="x")
        tk.Label(header, image=self._logo, bg=COLOR_PRIMARY).pack(side="left", padx=(18, 10), pady=12)
        tk.Label(
            header, text=APP_TITLE, bg=COLOR_PRIMARY, fg="white", font=(FONT_FAMILY, 17, "bold")
        ).pack(side="left")

    # ---------- piezas reutilizables ----------

    def _reset_view(self, title: str, hint: str) -> ttk.Frame:
        for child in self._content.winfo_children():
            child.destroy()
        self._password_entries = []
        self._error_var.set("")
        card = Card(self._content, padding=20)
        card.pack(fill="x")
        ttk.Label(card.body, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(card.body, text=hint, style="Hint.TLabel", wraplength=400).pack(
            anchor="w", pady=(2, 10)
        )
        return card.body

    def _label(self, parent: ttk.Frame, text: str) -> None:
        ttk.Label(parent, text=text, style="Card.TLabel", font=(FONT_FAMILY, 10, "bold")).pack(
            anchor="w", pady=(8, 2)
        )

    def _cedula_field(self, parent: ttk.Frame, variable: tk.StringVar, enabled: bool = True) -> ttk.Entry:
        self._label(parent, "Cédula")
        entry = ttk.Entry(
            parent,
            textvariable=variable,
            validate="key",
            validatecommand=self._cedula_check,
            state="normal" if enabled else "readonly",
        )
        entry.pack(fill="x")
        return entry

    def _password_field(self, parent: ttk.Frame, variable: tk.StringVar, caption: str) -> ttk.Entry:
        self._label(parent, caption)
        entry = ttk.Entry(
            parent, textvariable=variable, show="" if self._show_password.get() else PASSWORD_MASK
        )
        entry.pack(fill="x")
        self._password_entries.append(entry)
        return entry

    def _show_password_toggle(self, parent: ttk.Frame) -> None:
        ttk.Checkbutton(
            parent,
            text="👁  Mostrar contraseña",
            variable=self._show_password,
            command=self._apply_password_visibility,
            style="Card.TCheckbutton",
        ).pack(anchor="w", pady=(8, 0))

    def _apply_password_visibility(self) -> None:
        mask = "" if self._show_password.get() else PASSWORD_MASK
        for entry in self._password_entries:
            entry.configure(show=mask)

    def _error_label(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent, textvariable=self._error_var, style="Error.TLabel", wraplength=400, justify="left"
        ).pack(anchor="w", pady=(8, 0))

    def _button(self, parent: ttk.Frame, text: str, style: str, command: Callable[[], None]) -> ttk.Button:
        button = ttk.Button(parent, text=text, style=style, command=command)
        button.pack(fill="x", pady=(6, 0))
        return button

    def _fail(self, error: Exception) -> None:
        self._error_var.set(str(error))

    def _finish(self, user: User) -> None:
        self._result = user
        self._window.destroy()

    # ---------- vista: iniciar sesión ----------

    def _show_login(self, cedula: str = "", notice: str = "") -> None:
        body = self._reset_view("Iniciar sesión", notice or "Ingrese con su cédula y contraseña.")
        saved = self._users.remembered_users()
        if saved:
            ttk.Label(body, text="Entrar con un clic", style="CardTitle.TLabel").pack(anchor="w")
            for user in saved:
                self._saved_user_card(body, user)
            ttk.Separator(body).pack(fill="x", pady=(12, 4))
        cedula_var = tk.StringVar(value=cedula)
        password_var = tk.StringVar()
        cedula_entry = self._cedula_field(body, cedula_var)
        password_entry = self._password_field(body, password_var, "Contraseña")
        self._show_password_toggle(body)
        self._error_label(body)
        self._submit = lambda: self._login(cedula_var.get(), password_var.get())
        self._button(body, "Ingresar", "Primary.TButton", self._submit)
        links = ttk.Frame(body, style="Card.TFrame")
        links.pack(fill="x", pady=(6, 0))
        ttk.Button(links, text="Crear cuenta", style="Ghost.TButton", command=self._show_register).pack(
            side="left", expand=True, fill="x", padx=(0, 4)
        )
        ttk.Button(
            links,
            text="¿Olvidó su contraseña?",
            style="Ghost.TButton",
            command=lambda: self._show_recover(cedula_var.get()),
        ).pack(side="left", expand=True, fill="x", padx=(4, 0))
        (password_entry if cedula else cedula_entry).focus_set()

    def _saved_user_card(self, parent: ttk.Frame, user: User) -> None:
        card = tk.Frame(
            parent, bg="#EAF2FB", highlightthickness=1, highlightbackground=COLOR_BORDER, cursor="hand2"
        )
        card.pack(fill="x", pady=(6, 0))
        name = tk.Label(
            card, text=f"👤  {user.full_name}", bg="#EAF2FB", fg=COLOR_TEXT,
            font=(FONT_FAMILY, 11, "bold"), anchor="w", cursor="hand2",
        )
        name.pack(fill="x", padx=12, pady=(8, 0))
        detail = tk.Label(
            card, text=f"Cédula {user.cedula}  ·  clic para entrar", bg="#EAF2FB", fg=COLOR_MUTED,
            font=(FONT_FAMILY, 9), anchor="w", cursor="hand2",
        )
        detail.pack(fill="x", padx=12, pady=(0, 8))
        widgets = (card, name, detail)
        for widget in widgets:
            widget.bind("<Button-1>", lambda _event, item=user: self._enter_saved(item))
            widget.bind("<Enter>", lambda _event: [w.configure(bg=COLOR_SELECT) for w in widgets])
            widget.bind("<Leave>", lambda _event: [w.configure(bg="#EAF2FB") for w in widgets])

    def _enter_saved(self, user: User) -> None:
        try:
            self._finish(self._users.authenticate_remembered(user.cedula))
        except AppError as error:
            self._show_login(notice=str(error))

    def _login(self, cedula: str, password: str) -> None:
        if not cedula.strip() or not password:
            self._error_var.set("Escriba su cédula y su contraseña.")
            return
        try:
            user = self._users.authenticate(cedula.strip(), password)
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

    def _show_register(self, first_user: bool = False) -> None:
        hint = (
            "Cree el primer usuario del sistema."
            if first_user
            else "Se crea un solo usuario por cédula."
        )
        body = self._reset_view("Crear cuenta", hint)
        cedula_var, name_var = tk.StringVar(), tk.StringVar()
        password_var, confirm_var = tk.StringVar(), tk.StringVar()
        question_var, answer_var = tk.StringVar(value=SECURITY_QUESTIONS[0]), tk.StringVar()
        cedula_entry = self._cedula_field(body, cedula_var)
        self._label(body, "Apellidos y nombres")
        ttk.Entry(
            body, textvariable=name_var, validate="key", validatecommand=self._name_check
        ).pack(fill="x")
        self._password_field(body, password_var, "Contraseña (mínimo 8 caracteres)")
        self._password_field(body, confirm_var, "Repetir contraseña")
        self._show_password_toggle(body)
        self._label(body, "Pregunta de seguridad (para recuperar la cuenta)")
        ttk.Combobox(
            body, textvariable=question_var, values=SECURITY_QUESTIONS, state="readonly"
        ).pack(fill="x")
        self._label(body, "Respuesta")
        ttk.Entry(body, textvariable=answer_var).pack(fill="x")
        self._error_label(body)

        def submit() -> None:
            try:
                user = self._users.register(
                    cedula_var.get(), name_var.get(), password_var.get(), confirm_var.get(),
                    question_var.get(), answer_var.get(),
                )
            except AppError as error:
                self._fail(error)
                return
            self._show_login(user.cedula, "✔ Cuenta creada. Ahora inicie sesión.")

        self._submit = submit
        self._button(body, "Crear cuenta", "Success.TButton", submit)
        if self._users.has_users:
            self._button(body, "Volver", "Ghost.TButton", self._show_login)
        cedula_entry.focus_set()

    # ---------- vista: recuperar contraseña ----------

    def _show_recover(self, cedula: str = "") -> None:
        body = self._reset_view(
            "Recuperar contraseña", "Escriba su cédula para ver su pregunta de seguridad."
        )
        cedula_var = tk.StringVar(value=cedula)
        entry = self._cedula_field(body, cedula_var)
        self._error_label(body)

        def search() -> None:
            try:
                question = self._users.security_question(cedula_var.get().strip())
            except AppError as error:
                self._fail(error)
                return
            self._show_reset_form(cedula_var.get().strip(), question)

        self._submit = search
        self._button(body, "Continuar", "Primary.TButton", search)
        self._button(body, "Volver", "Ghost.TButton", self._show_login)
        entry.focus_set()

    def _show_reset_form(self, cedula: str, question: str) -> None:
        body = self._reset_view("Nueva contraseña", f"Cédula {cedula}")
        answer_var, password_var, confirm_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self._label(body, question)
        answer_entry = ttk.Entry(body, textvariable=answer_var)
        answer_entry.pack(fill="x")
        self._password_field(body, password_var, "Nueva contraseña (mínimo 8 caracteres)")
        self._password_field(body, confirm_var, "Repetir nueva contraseña")
        self._show_password_toggle(body)
        self._error_label(body)

        def submit() -> None:
            try:
                user = self._users.recover_password(
                    cedula, answer_var.get(), password_var.get(), confirm_var.get()
                )
            except AppError as error:
                self._fail(error)
                return
            self._show_login(user.cedula, "✔ Contraseña actualizada. Inicie sesión.")

        self._submit = submit
        self._button(body, "Cambiar contraseña", "Success.TButton", submit)
        self._button(body, "Volver", "Ghost.TButton", self._show_login)
        answer_entry.focus_set()
