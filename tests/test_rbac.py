"""Role authorization regression tests; synthetic signed sessions, not public role assignment."""
from fastapi.testclient import TestClient

from beninspeechlab.api import app
from beninspeechlab.core import ingest
from beninspeechlab.security import COOKIE, issue_session
from test_pipeline import wav_bytes


def role_client(role):
    client = TestClient(app)
    client.cookies.set(COOKIE, issue_session(role))
    csrf = client.get("/v1/admin/session")
    assert csrf.status_code == 200
    assert csrf.json()["role"] == role
    return client, {"X-CSRF-Token": csrf.json()["csrf_token"]}


def test_annotator_cannot_approve_export_or_read_stats(tmp_path, monkeypatch):
    monkeypatch.setenv("BENINSPEECH_DATA", str(tmp_path))
    uid = ingest(tmp_path, wav_bytes(), "speaker", True)["id"]
    client, headers = role_client("annotator")
    assert client.get("/v1/recordings").status_code == 200
    assert client.get(f"/v1/recordings/{uid}/audio").status_code == 200
    assert client.get("/v1/stats").status_code == 403
    assert client.get("/v1/export/asr").status_code == 403
    assert client.patch(f"/v1/recordings/{uid}/review", headers=headers, json={
        "transcript": "valid", "status": "approved"
    }).status_code == 403
    assert client.patch(f"/v1/recordings/{uid}/review", headers=headers, json={
        "transcript": "valid", "status": "pending_review"
    }).status_code == 200


def test_manager_can_approve_but_not_export(tmp_path, monkeypatch):
    monkeypatch.setenv("BENINSPEECH_DATA", str(tmp_path))
    uid = ingest(tmp_path, wav_bytes(), "speaker", True)["id"]
    client, headers = role_client("manager")
    assert client.get("/v1/stats").status_code == 200
    assert client.get("/v1/export/asr").status_code == 403
    assert client.patch(f"/v1/recordings/{uid}/review", headers=headers, json={
        "transcript": "valid", "status": "approved"
    }).status_code == 200


def test_tampered_role_cookie_is_rejected():
    client, _ = role_client("annotator")
    token = client.cookies.get(COOKIE)
    client.cookies.set(COOKIE, token.replace(".annotator.", ".super_admin."))
    assert client.get("/v1/export/asr").status_code == 401
