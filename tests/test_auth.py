from __future__ import annotations

from pathlib import Path

import pytest

from asistencia.auth import LoginThrottle, UserRepository
from asistencia.config import LOCKOUT_SECONDS, SECURITY_QUESTIONS
from asistencia.errors import AuthError, ValidationError

CEDULA = "1710034065"
OTHER_CEDULA = "0926687856"
QUESTION = SECURITY_QUESTIONS[0]


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def repo(tmp_path: Path, clock: FakeClock) -> UserRepository:
    return UserRepository(tmp_path / "usuarios.json", clock)


def register(
    repo: UserRepository, cedula: str = CEDULA, password: str = "Clave1234", username: str = "juan.perez"
):
    return repo.register(
        cedula, "perez lopez juan", username, password, password, QUESTION, "Firulais"
    )


def test_registro_guarda_nombre_en_mayusculas_y_no_guarda_la_clave(repo, tmp_path) -> None:
    user = register(repo)
    assert user.full_name == "PEREZ LOPEZ JUAN"
    text = (tmp_path / "usuarios.json").read_text(encoding="utf-8")
    assert "Clave1234" not in text and "firulais" not in text.lower()


def test_login_correcto_e_incorrecto(repo) -> None:
    register(repo)
    assert repo.authenticate("juan.perez", "Clave1234").cedula == CEDULA
    with pytest.raises(AuthError):
        repo.authenticate("juan.perez", "otra-clave")
    with pytest.raises(AuthError):
        repo.authenticate("nadie", "Clave1234")


@pytest.mark.parametrize(
    ("cedula", "password", "confirmation"),
    [
        ("1234567890", "Clave1234", "Clave1234"),
        (CEDULA, "corta", "corta"),
        (CEDULA, "Clave1234", "Clave9999"),
    ],
)
def test_registro_valida_entradas(repo, cedula, password, confirmation) -> None:
    with pytest.raises(ValidationError):
        repo.register(cedula, "PEREZ JUAN", "juan.perez", password, confirmation, QUESTION, "Firulais")
    assert not repo.has_users


def test_una_sola_cuenta_por_cedula(repo) -> None:
    register(repo)
    with pytest.raises(ValidationError):
        register(repo)


def test_pregunta_fuera_de_la_lista_se_rechaza(repo) -> None:
    with pytest.raises(ValidationError):
        repo.register(CEDULA, "PEREZ JUAN", "juan.perez", "Clave1234", "Clave1234", "¿Inventada?", "algo")


def test_bloqueo_tras_intentos_fallidos_y_desbloqueo(repo, clock) -> None:
    register(repo)
    for _ in range(5):
        with pytest.raises(AuthError):
            repo.authenticate("juan.perez", "mal")
    with pytest.raises(AuthError, match="Espere"):
        repo.authenticate("juan.perez", "Clave1234")
    clock.now += LOCKOUT_SECONDS + 1
    assert repo.authenticate("juan.perez", "Clave1234").cedula == CEDULA


def test_throttle_se_reinicia_con_un_acierto() -> None:
    clock = FakeClock()
    throttle = LoginThrottle(clock, max_attempts=3, lockout_seconds=10)
    throttle.register_failure("a")
    throttle.register_failure("a")
    throttle.reset("a")
    throttle.register_failure("a")
    throttle.check("a")


def test_recuperar_clave_ignora_mayusculas_y_tildes(repo) -> None:
    repo.register(CEDULA, "PEREZ JUAN", "juan.perez", "Clave1234", "Clave1234", QUESTION, "Perú Ñandú")
    assert repo.security_question("juan.perez") == QUESTION
    with pytest.raises(AuthError):
        repo.recover_password("juan.perez", "otra", "Nueva12345", "Nueva12345")
    repo.recover_password("juan.perez", "  peru   NANDU ", "Nueva12345", "Nueva12345")
    assert repo.authenticate("juan.perez", "Nueva12345").cedula == CEDULA
    with pytest.raises(AuthError):
        repo.authenticate("juan.perez", "Clave1234")


def test_recuperar_clave_valida_la_nueva_clave(repo) -> None:
    register(repo)
    with pytest.raises(ValidationError):
        repo.recover_password("juan.perez", "Firulais", "Nueva12345", "distinta")
    assert repo.authenticate("juan.perez", "Clave1234")


def test_usuario_guardado_persiste_y_se_puede_desactivar(repo, tmp_path, clock) -> None:
    register(repo)
    register(repo, OTHER_CEDULA, username="otro.user")
    repo.set_remembered(CEDULA, True)
    reloaded = UserRepository(tmp_path / "usuarios.json", clock)
    assert [u.cedula for u in reloaded.remembered_users()] == [CEDULA]
    assert reloaded.authenticate_remembered(CEDULA).cedula == CEDULA
    reloaded.set_remembered(CEDULA, False)
    assert reloaded.remembered_users() == ()
    with pytest.raises(AuthError):
        reloaded.authenticate_remembered(CEDULA)


def test_archivo_corrupto_se_respalda_y_avisa(tmp_path, clock) -> None:
    path = tmp_path / "usuarios.json"
    path.write_text("{no es json", encoding="utf-8")
    repo = UserRepository(path, clock)
    assert repo.load_warning is not None and not repo.has_users
    assert (tmp_path / "usuarios.corrupto").exists()


def test_no_se_repite_el_usuario_aunque_cambien_mayusculas(repo) -> None:
    register(repo)
    assert repo.username_taken("JUAN.Perez")
    with pytest.raises(ValidationError, match="usuario"):
        register(repo, OTHER_CEDULA, username="Juan.PEREZ")
    assert repo.authenticate("JUAN.PEREZ", "Clave1234").cedula == CEDULA


@pytest.mark.parametrize("username", ["", "ab", "1juan", "juan perez", "juan@mail", "x" * 21])
def test_usuario_invalido_se_rechaza(repo, username) -> None:
    with pytest.raises(ValidationError):
        register(repo, username=username)


def test_cuenta_antigua_sin_usuario_usa_la_cedula(repo, tmp_path, clock) -> None:
    register(repo)
    path = tmp_path / "usuarios.json"
    import json

    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["users"][0]["username"]
    path.write_text(json.dumps(raw), encoding="utf-8")
    legacy = UserRepository(path, clock)
    assert legacy.authenticate(CEDULA, "Clave1234").username == CEDULA
