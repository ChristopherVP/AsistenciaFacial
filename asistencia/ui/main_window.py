from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from PIL import ImageTk

from ..branding import make_logo
from ..config import (
    APP_TITLE,
    COLOR_PRIMARY,
    DAY_LABELS,
    FONT_FAMILY,
)
from .attendance_tab import AttendanceTab
from .courses_tab import CoursesTab
from .settings_tab import SettingsTab
from .state import AppState


class MainWindow:
    def __init__(
        self,
        root: tk.Tk,
        state: AppState,
        icon: ImageTk.PhotoImage,
        warnings: list[str],
    ) -> None:
        self._root = root
        self._state = state
        self._icon = icon
        self._header_logo = ImageTk.PhotoImage(make_logo(44))
        self._clock_var = tk.StringVar()
        root.title(APP_TITLE)
        root.geometry("1120x780")
        root.minsize(1040, 740)
        self._build_header()
        self._attendance = AttendanceTab(self._build_notebook_host(), state)
        self._notebook.add(self._attendance, text="  Tomar lista  ")
        self._courses = CoursesTab(self._notebook, state)
        self._notebook.add(self._courses, text="  Cursos  ")
        self._settings = SettingsTab(self._notebook, state)
        self._notebook.add(self._settings, text="  Ajustes  ")
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        for warning in warnings:
            messagebox.showwarning(APP_TITLE, warning, parent=root)
        self._tick()
        root.after(400, self._settings.refresh_cameras)

    def _build_header(self) -> None:
        header = tk.Frame(self._root, bg=COLOR_PRIMARY, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, image=self._header_logo, bg=COLOR_PRIMARY).pack(side="left", padx=(16, 8))
        tk.Label(
            header,
            text=APP_TITLE,
            bg=COLOR_PRIMARY,
            fg="white",
            font=(FONT_FAMILY, 18, "bold"),
        ).pack(side="left")
        tk.Label(
            header,
            textvariable=self._clock_var,
            bg=COLOR_PRIMARY,
            fg="#D6EAF8",
            font=(FONT_FAMILY, 11),
        ).pack(side="right", padx=20)

    def _build_notebook_host(self) -> ttk.Notebook:
        self._notebook = ttk.Notebook(self._root)
        self._notebook.pack(fill="both", expand=True, padx=8, pady=(8, 8))
        return self._notebook

    def _tick(self) -> None:
        self._root.after(1000, self._tick)
        now = datetime.now()
        self._clock_var.set(f"{DAY_LABELS[now.weekday()]} {now:%d/%m/%Y   %H:%M:%S}")
        self._attendance.on_tick(now)

    def _on_close(self) -> None:
        if self._attendance.is_running:
            if not messagebox.askyesno(
                APP_TITLE, "Hay una lista en curso.\n¿Finalizar y guardar antes de salir?"
            ):
                return
            self._attendance.finish_session()
        self._root.destroy()
