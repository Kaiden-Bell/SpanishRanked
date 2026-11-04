from fastapi.testclient import TestClient

from app import db
from app.config import Settings
from app.main import create_app


def make_settings(tmp_path):
    return Settings(data_dir=tmp_path / "data", frontend_dist=tmp_path / "no-dist")


def test_health_reports_schema_version(tmp_path):
    with TestClient(create_app(make_settings(tmp_path))) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "schema_version": len(db.MIGRATIONS)}


def test_data_survives_app_recreation(tmp_path):
    settings = make_settings(tmp_path)

    def users():
        conn = db.connect(settings.db_path)
        try:
            return [tuple(r) for r in conn.execute("SELECT username, password_hash FROM users")]
        finally:
            conn.close()

    with TestClient(create_app(settings)):
        first = users()
    with TestClient(create_app(settings)):
        second = users()
    # The bootstrap owner is created once; a restart must neither duplicate nor re-key it.
    assert len(first) == 1
    assert second == first


def test_health_returns_503_when_database_is_unavailable(tmp_path):
    # No lifespan: the data directory was never created, so the DB cannot be opened.
    client = TestClient(create_app(make_settings(tmp_path)))
    assert client.get("/api/health").status_code == 503


def test_frontend_is_served_but_does_not_shadow_api(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>frontend-marker</html>")
    settings = Settings(data_dir=tmp_path / "data", frontend_dist=dist)
    with TestClient(create_app(settings)) as client:
        assert client.get("/").text == "<html>frontend-marker</html>"
        assert client.get("/api/health").json()["status"] == "ok"
