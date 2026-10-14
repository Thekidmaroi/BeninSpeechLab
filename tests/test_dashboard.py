from fastapi.testclient import TestClient
from beninspeechlab.api import app
from beninspeechlab.core import corpus_stats, ingest, review_recording
from test_pipeline import wav_bytes


def test_empty_dashboard(tmp_path, monkeypatch):
    monkeypatch.setenv("BENINSPEECH_DATA", str(tmp_path))
    result = TestClient(app).get("/v1/stats")
    assert result.status_code == 200
    assert result.json() == {
        "total_recordings": 0, "distinct_speakers": 0,
        "total_duration_s": 0.0, "pending_review": 0,
        "approved": 0, "rejected": 0, "validation_percent": 0.0,
        "approved_duration_s": 0.0,
    }


def test_dashboard_after_reviews(tmp_path, monkeypatch):
    monkeypatch.setenv("BENINSPEECH_DATA", str(tmp_path))
    a = ingest(tmp_path, wav_bytes(seconds=1), "speaker_a", True)["id"]
    b = ingest(tmp_path, wav_bytes(seconds=2), "speaker_b", True)["id"]
    c = ingest(tmp_path, wav_bytes(seconds=3), "speaker_a", True)["id"]
    review_recording(tmp_path, a, "Transcription vérifiée", "approved")
    review_recording(tmp_path, b, "", "rejected")
    stats = corpus_stats(tmp_path)
    assert stats["total_recordings"] == 3
    assert stats["distinct_speakers"] == 2
    assert stats["total_duration_s"] == 6
    assert stats["approved_duration_s"] == 1
    assert stats["approved"] == 1
    assert stats["rejected"] == 1
    assert stats["pending_review"] == 1
    assert stats["validation_percent"] == 33.3
    assert TestClient(app).get("/v1/stats").json() == stats
