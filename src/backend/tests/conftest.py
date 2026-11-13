import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db, security
from app.config import Settings
from app.main import create_app
from app.security import hash_password

BOOTSTRAP_PASSWORD = "bootstrap-password"
NEW_PASSWORD = "a-much-better-password"


@pytest.fixture(autouse=True)
def cheap_password_hashing(monkeypatch):
    # Production scrypt cost makes every login take ~0.1s; verification reads the cost from the
    # stored hash, so tests can hash cheaply without changing what is being checked.
    monkeypatch.setattr(security, "_N", 2**4)


# A small, fixed verb set keeps tests fast and independent of a locally built full database.
TEST_VERBS = (
    "extrañar,hablar,ir,ser,decir,ver,querer,gustar,casar,comer,vivir,poder,viajar,tener,estar,hacer,"
    "necesitar,llegar,salir,volver,dormir,pensar,jugar,escribir,leer,trabajar,cantar,bailar,buscar,llamar"
)


@pytest.fixture(scope="session")
def verb_data_path(tmp_path_factory):
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_verb_data.py"
    spec = importlib.util.spec_from_file_location("build_verb_data", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    out = tmp_path_factory.mktemp("verbs") / "verbs.db"
    module.build(out, TEST_VERBS.split(","))
    return out


@pytest.fixture
def settings(tmp_path, verb_data_path):
    return Settings(data_dir=tmp_path / "data", frontend_dist=tmp_path / "no-dist", verb_data_path=verb_data_path)


def set_owner_password(settings, password, must_change=True):
    """The real bootstrap password is random and only logged, so tests replace it."""
    conn = db.connect(settings.db_path)
    with conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, must_change_password = ? WHERE username = 'owner'",
            (hash_password(password), int(must_change)),
        )
    conn.close()


def sign_in(client, password):
    """Log in and attach the CSRF header the way the frontend does."""
    response = client.post("/api/auth/login", json={"username": "owner", "password": password})
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        set_owner_password(settings, BOOTSTRAP_PASSWORD)
        yield c


@pytest.fixture
def authed(client):
    """Signed in, bootstrap password already replaced."""
    sign_in(client, BOOTSTRAP_PASSWORD)
    r = client.post(
        "/api/auth/change-password",
        json={"current_password": BOOTSTRAP_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert r.status_code == 200, r.text
    return client


@pytest.fixture
def raw_db(settings):
    conn = db.connect(settings.db_path)
    yield conn
    conn.close()
