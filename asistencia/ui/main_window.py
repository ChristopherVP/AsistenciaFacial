from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from PIL import ImageTk

from ..branding import make_logo
from ..config import (
    APP_TITLE,
    COLOR_ACCENT,
    COLOR_PRIMARY,
    COLOR_PRIMARY_DARK,
    DAY_LABELS,
    FONT_FAMILY,
)
from .attendance_tab import AttendanceTab
from .courses_tab import CoursesTab
from .scrollable import ScrollableFrame
from .settings_tab import SettingsTab
from .state import AppState
from .window_utils import maximize


class MainWindow:
    def __init__(
        self,
        root: tk.Tk,
        state: AppState,
        icon: ImageTk.PhotoImage,
        warnings: list[str],
    ) -> None:
        self.logout_requested = False
        self._tick_job: str | None = None
        self._camera_job: str | None = None
        self._root = root
        self._state = state
        self._icon = icon
        self._header_logo = ImageTk.PhotoImage(make_logo(46))
        self._clock_var = tk.StringVar()
        root.title(APP_TITLE)
        root.minsize(1100, 520)
        maximize(root)
        self._build_header()
        self._notebook = ttk.Notebook(root)
        self._notebook.pack(fill="both", expand=True, padx=8, pady=(8, 8))
        self._attendance = self._add_tab(AttendanceTab, "  📷  Tomar lista  ")
        self._courses = self._add_tab(CoursesTab, "  📚  Cursos  ")
        self._settings = self._add_tab(SettingsTab, "  ⚙  Ajustes  ")
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        for warning in warnings:
            messagebox.showwarning(APP_TITLE, warning, parent=root)
        self._tick()
        self._camera_job = root.after(400, self._settings.refresh_cameras)

    def _build_header(self) -> None:
        header = tk.Frame(self._root, bg=COLOR_PRIMARY, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, image=self._header_logo, bg=COLOR_PRIMARY).pack(side="left", padx=(18, 10))
        titles = tk.Frame(header, bg=COLOR_PRIMARY)
        titles.pack(side="left")
        tk.Label(
            titles, text=APP_TITLE, bg=COLOR_PRIMARY, fg="white", font=(FONT_FAMILY, 18, "bold")
        ).pack(anchor="w")
        tk.Label(
            titles,
            text="Control de asistencia con reconocimiento facial",
            bg=COLOR_PRIMARY,
            fg="#D6EAF8",
            font=(FONT_FAMILY, 9),
        ).pack(anchor="w")
        tk.Label(
            header, textvariable=self._clock_var, bg=COLOR_PRIMARY, fg="#D6EAF8", font=(FONT_FAMILY, 11)
        ).pack(side="right", padx=20)
        tk.Button(
            header,
            text="Cerrar sesión",
            command=self._logout,
            bg=COLOR_PRIMARY_DARK,
            fg="white",
            activebackground=COLOR_ACCENT,
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            font=(FONT_FAMILY, 10, "bold"),
            padx=12,
            pady=6,
        ).pack(side="right")
        user = self._state.current_user
        if user is not None:
            tk.Label(
                header,
                text=f"👤  {user.full_name}",
                bg=COLOR_PRIMARY,
                fg="white",
                font=(FONT_FAMILY, 10, "bold"),
            ).pack(side="right", padx=14)

    def _add_tab(self, factory, title: str):
        holder = ScrollableFrame(self._notebook)
        content = factory(holder.body, self._state)
        content.pack(fill="both", expand=True)
        self._notebook.add(holder, text=title)
        return content

    def _tick(self) -> None:
        self._tick_job = self._root.after(1000, self._tick)
        now = datetime.now()
        self._clock_var.set(f"{DAY_LABELS[now.weekday()]} {now:%d/%m/%Y   %H:%M:%S}")
        self._attendance.on_tick(now)

    def _confirm_end_session(self, action: str) -> bool:
        if not self._attendance.is_running:
            return True
        if not messagebox.askyesno(
            APP_TITLE, f"Hay una lista en curso.\n¿Finalizar y guardar antes de {action}?"
        ):
            return False
        self._attendance.finish_session()
        return True

    def _logout(self) -> None:
        if self._confirm_end_session("cerrar sesión"):
            self.logout_requested = True
            self._root.quit()

    def _on_close(self) -> None:
        if self._confirm_end_session("salir"):
            self._root.quit()

    def close(self) -> None:
        for job in (self._tick_job, self._camera_job):
            if job is not None:
                self._root.after_cancel(job)
        for child in self._root.winfo_children():
            child.destroy()
