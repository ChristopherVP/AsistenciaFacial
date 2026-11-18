from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox

import cv2

from asistencia.branding import Splash, install_icon, prepare_windows_identity
from asistencia.config import APP_TITLE
from asistencia.errors import ModelError
from asistencia.face_engine import FaceEngine
from asistencia.storage import CourseRepository, SettingsRepository
from asistencia.ui.main_window import MainWindow
from asistencia.ui.state import AppState
from asistencia.ui.theme import apply_theme


def main() -> None:
    prepare_windows_identity()
    root = tk.Tk()
    root.withdraw()
    apply_theme(root)
    icon = install_icon(root)
    splash = Splash(root)
    try:
        splash.report("Cargando cursos y ajustes…", 0.02)
        repository = CourseRepository()
        settings_repository = SettingsRepository()
        settings, settings_warning = settings_repository.load()
        engine = FaceEngine(on_progress=splash.report)
        splash.report("Todo listo", 1.0)
        splash.hold(0.9)
    except (ModelError, cv2.error) as error:
        splash.close()
        messagebox.showerror(APP_TITLE, str(error), parent=root)
        root.destroy()
        sys.exit(1)
    splash.close()
    warnings = [*repository.load_warnings]
    if settings_warning:
        warnings.append(settings_warning)
    state = AppState(engine, repository, settings_repository, settings)
    MainWindow(root, state, icon, warnings)
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
