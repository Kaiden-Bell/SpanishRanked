import re

from app import db, manage
from app.security import verify_password

from conftest import BOOTSTRAP_PASSWORD, NEW_PASSWORD, sign_in


def owner(conn):
    return conn.execute("SELECT password_hash, must_change_password FROM users WHERE username = 'owner'").fetchone()


def test_reset_issues_a_new_one_time_password(authed, raw_db):
    password = manage.reset_owner_password(raw_db)
    row = owner(raw_db)
    assert verify_password(password, row["password_hash"])
    assert not verify_password(NEW_PASSWORD, row["password_hash"])  # the lost password is dead
    assert row["must_change_password"] == 1  # forced change applies again


def test_reset_signs_out_existing_sessions(authed, raw_db):
    assert authed.get("/api/auth/me").status_code == 200
    manage.reset_owner_password(raw_db)
    assert authed.get("/api/auth/me").status_code == 401


def test_reset_then_full_login_flow_works(client, raw_db):
    password = manage.reset_owner_password(raw_db)
    assert sign_in(client, password).json()["must_change_password"] is True
    r = client.post("/api/auth/change-password", json={"current_password": password, "new_password": NEW_PASSWORD})
    assert r.status_code == 200
    assert client.get("/api/study-sessions").status_code == 200


def test_reset_without_an_owner_changes_nothing(tmp_path):
    conn = db.connect(tmp_path / "x.db")
    db.migrate(conn)
    assert manage.reset_owner_password(conn) is None
    conn.close()


def test_cli_prints_the_password(client, settings, monkeypatch, capsys):
    monkeypatch.setenv("LANGUAGEAI_DATA_DIR", str(settings.data_dir))
    assert manage.main(["reset-owner-password"]) == 0
    printed = re.search(r"one-time password: (\S+)", capsys.readouterr().out).group(1)
    conn = db.connect(settings.db_path)
    assert verify_password(printed, owner(conn)["password_hash"])
    assert not verify_password(BOOTSTRAP_PASSWORD, owner(conn)["password_hash"])
    conn.close()


def test_cli_refuses_to_create_a_database(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LANGUAGEAI_DATA_DIR", str(tmp_path / "empty"))
    assert manage.main(["reset-owner-password"]) == 1
    assert not (tmp_path / "empty").exists()
    assert "start the app once first" in capsys.readouterr().err
