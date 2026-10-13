import io
import wave
import pytest
from beninspeechlab.core import ingest, manifest, export_manifest

def wav_bytes(seconds=1, rate=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))
    return buf.getvalue()

def test_consent_required(tmp_path):
    with pytest.raises(ValueError, match="consent"):
        ingest(tmp_path, wav_bytes(), "speaker-1", False)

def test_ingest_and_deduplicate(tmp_path):
    audio = wav_bytes()
    first = ingest(tmp_path, audio, "speaker-1", True)
    second = ingest(tmp_path, audio, "speaker-1", True)
    assert not first["duplicate"] and second["duplicate"]
    assert first["id"] == second["id"]
    assert manifest(tmp_path) == []
    assert len(manifest(tmp_path, approved_only=False)) == 1

def test_invalid_audio(tmp_path):
    with pytest.raises(ValueError):
        ingest(tmp_path, b"not audio", "speaker-1", True)

def test_manifest_requires_approval(tmp_path):
    ingest(tmp_path, wav_bytes(), "speaker-1", True, transcript="Test")
    out = tmp_path / "manifest.jsonl"
    assert export_manifest(tmp_path, out) == 0
    assert out.read_text() == ""
