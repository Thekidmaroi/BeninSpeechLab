import io
import json
from zipfile import ZipFile

from fastapi.testclient import TestClient

from beninspeechlab.api import app
from beninspeechlab.core import build_asr_export, ingest, review_recording
from test_pipeline import wav_bytes


def test_export_only_release_approved(tmp_path, monkeypatch):
    monkeypatch.setenv("BENINSPEECH_DATA", str(tmp_path))
    audio = wav_bytes()
    released = ingest(tmp_path, audio, "speaker-release", True,
                      license_scope="dataset_release_approved")["id"]
    internal = ingest(tmp_path, audio, "speaker-internal", True)["id"]
    pending = ingest(tmp_path, audio, "speaker-pending", True,
                     license_scope="dataset_release_approved")["id"]
    review_recording(tmp_path, released, "Mì do gbe", "approved")
    review_recording(tmp_path, internal, "Internal only", "approved")
    client = TestClient(app)
    response = client.get("/v1/export/asr")
    assert response.status_code == 200
    with ZipFile(io.BytesIO(response.content)) as archive:
        names = set(archive.namelist())
        assert names == {"manifest.jsonl", f"audio/{released}.wav"}
        rows = [json.loads(line) for line in
                archive.read("manifest.jsonl").decode("utf-8").splitlines()]
        assert len(rows) == 1
        assert rows[0]["id"] == released
        assert rows[0]["text"] == "Mì do gbe"
        assert rows[0]["audio"] == f"audio/{released}.wav"
        assert archive.read(rows[0]["audio"]) == audio
        assert internal not in str(rows)
        assert pending not in str(rows)


def test_export_empty_zip(tmp_path, monkeypatch):
    monkeypatch.setenv("BENINSPEECH_DATA", str(tmp_path))
    response = TestClient(app).get("/v1/export/asr")
    assert response.status_code == 200
    with ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.namelist() == ["manifest.jsonl"]
        assert archive.read("manifest.jsonl") == b""


def test_export_rejects_missing_audio(tmp_path):
    uid = ingest(tmp_path, wav_bytes(), "speaker-release", True,
                 license_scope="dataset_release_approved")["id"]
    review_recording(tmp_path, uid, "Verified", "approved")
    (tmp_path / "private_audio" / f"{uid}.wav").unlink()
    try:
        build_asr_export(tmp_path, tmp_path / "output.zip")
        assert False, "Expected missing audio error"
    except ValueError as exc:
        assert "Missing or unsafe" in str(exc)
