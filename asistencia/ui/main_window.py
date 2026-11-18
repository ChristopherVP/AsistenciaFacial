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
from .scrollable import ScrollableFrame
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
        width = min(1120, root.winfo_screenwidth() - 60)
        height = min(780, root.winfo_screenheight() - 110)
        root.geometry(f"{width}x{height}+30+20")
        root.minsize(1040, 520)
        self._build_header()
        self._build_notebook_host()
        self._attendance = self._add_tab(AttendanceTab, "  Tomar lista  ")
        self._courses = self._add_tab(CoursesTab, "  Cursos  ")
        self._settings = self._add_tab(SettingsTab, "  Ajustes  ")
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

    def _add_tab(self, factory, title: str):
        holder = ScrollableFrame(self._notebook)
        content = factory(holder.body, self._state)
        content.pack(fill="both", expand=True)
        self._notebook.add(holder, text=title)
        return content

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
