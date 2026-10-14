from fastapi.testclient import TestClient

from beninspeechlab.api import app
from beninspeechlab.core import ingest
from conftest import login_admin
from test_pipeline import wav_bytes


def test_public_and_private_pages(tmp_path, monkeypatch):
    monkeypatch.setenv("BENINSPEECH_DATA", str(tmp_path))
    client = TestClient(app)
    assert client.get("/contribute").status_code == 200
    assert client.get("/admin/login").status_code == 200
    assert client.get("/admin").status_code == 401
    assert client.get("/v1/recordings").status_code == 401
    assert client.get("/v1/stats").status_code == 401
    assert client.get("/v1/export/asr").status_code == 401
    assert client.get("/studio", follow_redirects=False).headers["location"] == "/admin"
    assert "no-store" in client.get("/contribute").headers["cache-control"]


def test_login_csrf_and_logout(tmp_path, monkeypatch):
    monkeypatch.setenv("BENINSPEECH_DATA", str(tmp_path))
    uid = ingest(tmp_path, wav_bytes(), "speaker", True)["id"]
    client = TestClient(app)
    assert client.post("/v1/admin/login", json={"password": "wrong"},
                       follow_redirects=False).status_code == 401
    csrf = login_admin(client)
    assert client.get("/admin").status_code == 200
    assert client.patch(f"/v1/recordings/{uid}/review",
                        json={"status": "approved", "transcript": "test"}).status_code == 403
    assert client.patch(f"/v1/recordings/{uid}/review",
                        json={"status": "approved", "transcript": "test"},
                        headers={**csrf, "Origin": "https://evil.example"}).status_code == 403
    assert client.patch(f"/v1/recordings/{uid}/review",
                        json={"status": "approved", "transcript": "test"},
                        headers=csrf).status_code == 200
    assert client.post("/v1/admin/logout", headers=csrf,
                       follow_redirects=False).status_code == 303
    assert client.get("/v1/stats").status_code == 401


def test_unconfigured_admin_fails_closed(monkeypatch):
    monkeypatch.delenv("BENINSPEECH_ADMIN_PASSWORD")
    client = TestClient(app)
    assert client.get("/admin").status_code == 401
    assert client.post("/v1/admin/login", json={"password": "anything"}).status_code == 503


def test_public_upload_rejects_cross_origin(tmp_path, monkeypatch):
    monkeypatch.setenv("BENINSPEECH_DATA", str(tmp_path))
    response = TestClient(app).post(
        "/v1/recordings", data={"speaker_id": "speaker", "consent": "true"},
        files={"file": ("audio.wav", wav_bytes(), "audio/wav")},
        headers={"Origin": "https://evil.example"}
    )
    assert response.status_code == 403
