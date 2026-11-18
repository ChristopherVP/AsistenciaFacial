from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from openpyxl import Workbook, load_workbook

from asistencia.attendance import PERCENT_HEADER, AttendanceBook
from asistencia.face_engine import Gallery
from asistencia.models import Student


def make_student(student_id: str, name: str, seed: int) -> Student:
    vector = np.random.default_rng(seed).normal(size=128)
    return Student(student_id, name, (tuple(float(v) for v in vector),))


@pytest.fixture
def students() -> tuple[Student, ...]:
    return (make_student("111", "ANDRADE ANA", 1), make_student("222", "BRAVO BETO", 2))


def test_excel_tiene_columna_porcentaje_y_formula(tmp_path: Path, students) -> None:
    book = AttendanceBook(tmp_path / "curso.xlsx")
    column = book.start_list(datetime(2026, 11, 18, 7, 0), students)
    book.finalize(column, frozenset({"111"}), students)
    sheet = load_workbook(tmp_path / "curso.xlsx").active
    assert [sheet.cell(1, c).value for c in (1, 2, 3)] == ["Cédula", "Apellidos y nombres", PERCENT_HEADER]
    assert column == 4
    assert sheet.cell(2, 3).value.startswith("=IF(COUNT(D2:XFD2)=0")
    assert sheet.cell(2, 3).number_format == "0%"
    assert (sheet.cell(2, 4).value, sheet.cell(3, 4).value) == (1, 0)


def test_porcentaje_ignora_listas_anteriores_al_ingreso(tmp_path: Path, students) -> None:
    book = AttendanceBook(tmp_path / "curso.xlsx")
    first = book.start_list(datetime(2026, 11, 18, 7, 0), students[:1])
    book.finalize(first, frozenset({"111"}), students[:1])
    second = book.start_list(datetime(2026, 11, 19, 7, 0), students)
    book.finalize(second, frozenset(), students)
    sheet = load_workbook(tmp_path / "curso.xlsx").active
    ana, beto = (2, 3) if sheet.cell(2, 1).value == "111" else (3, 2)
    assert [sheet.cell(ana, c).value for c in (4, 5)] == [1, 0]  # 1 de 2 = 50 %
    assert [sheet.cell(beto, c).value for c in (4, 5)] == [None, 0]  # solo cuenta su lista


def test_excel_antiguo_se_migra_sin_perder_fechas(tmp_path: Path) -> None:
    path = tmp_path / "viejo.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Cédula", "Apellidos y nombres", datetime(2026, 11, 1, 7, 0)])
    sheet.append(["111", "ANDRADE ANA", 1])
    workbook.save(path)
    AttendanceBook(path).sync_students((make_student("111", "ANDRADE ANA", 1),))
    migrated = load_workbook(path).active
    assert migrated.cell(1, 3).value == PERCENT_HEADER
    assert migrated.cell(1, 4).value == datetime(2026, 11, 1, 7, 0)
    assert migrated.cell(2, 4).value == 1


def test_finalize_solo_cuenta_estudiantes_del_curso(tmp_path: Path, students) -> None:
    book = AttendanceBook(tmp_path / "curso.xlsx")
    column = book.start_list(datetime(2026, 11, 18, 7, 0), students)
    result = book.finalize(column, frozenset({"111", "999"}), students[:1])
    assert (result.present, result.total) == (1, 1)


def test_rostro_duplicado_se_detecta_aunque_cambie_la_cedula(students) -> None:
    gallery = Gallery(students)
    same_face = students[0].embeddings
    assert gallery.best_match(same_face, 0.40) == students[0]


def test_rostro_distinto_no_es_duplicado(students) -> None:
    stranger = make_student("333", "CEVALLOS CARLA", 99)
    assert Gallery(students).best_match(stranger.embeddings, 0.40) is None


def test_galeria_vacia_no_falla() -> None:
    assert Gallery(()).best_match(((0.1,) * 128,), 0.40) is None


def test_snapshot_de_lista_nunca_da_faltas_negativas() -> None:
    pytest.importorskip("tkinter")
    from asistencia.ui.attendance_tab import ListSnapshot

    snapshot = ListSnapshot(
        "curso", datetime.now(), frozenset({"111"}), {"111": datetime.now(), "999": datetime.now()}
    )
    assert (snapshot.present_count, snapshot.absent_count) == (1, 0)
