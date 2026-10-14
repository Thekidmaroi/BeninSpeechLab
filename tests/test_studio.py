import pytest
from fastapi.testclient import TestClient
from beninspeechlab.api import app
from beninspeechlab.core import ingest, manifest
from test_pipeline import wav_bytes


def test_library_review_and_audio(tmp_path, monkeypatch):
    monkeypatch.setenv("BENINSPEECH_DATA", str(tmp_path))
    uid = ingest(tmp_path, wav_bytes(), "speaker_001", True)["id"]
    client = TestClient(app)
    listed = client.get("/v1/recordings")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == uid
    audio = client.get(f"/v1/recordings/{uid}/audio")
    assert audio.status_code == 200
    assert audio.content[:4] == b"RIFF"
    assert client.patch(f"/v1/recordings/{uid}/review", json={
        "transcript": "", "status": "approved"
    }).status_code == 422
    result = client.patch(f"/v1/recordings/{uid}/review", json={
        "transcript": "Bonjour en fon", "status": "approved"
    })
    assert result.status_code == 200
    assert result.json()["status"] == "approved"
    assert len(manifest(tmp_path)) == 1
    assert client.get("/studio").status_code == 200


def test_review_invalid_and_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("BENINSPEECH_DATA", str(tmp_path))
    client = TestClient(app)
    assert client.get("/v1/recordings/does-not-exist/audio").status_code == 404
    assert client.patch("/v1/recordings/does-not-exist/review", json={
        "status": "approved", "transcript": "text"
    }).status_code == 404
    uid = ingest(tmp_path, wav_bytes(), "speaker_002", True)["id"]
    assert client.patch(f"/v1/recordings/{uid}/review", json={
        "status": "invalid", "transcript": "text"
    }).status_code == 422
