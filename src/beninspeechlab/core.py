"""Minimal auditable WAV ingestion; no audio is public by default."""
import hashlib
import io
import json
import os
import sqlite3
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path

MAX_BYTES = 20 * 1024 * 1024


def init_db(root: Path) -> sqlite3.Connection:
    root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(root / "metadata.sqlite3")
    conn.execute("""CREATE TABLE IF NOT EXISTS recordings (
        id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, speaker_id TEXT NOT NULL,
        language TEXT NOT NULL, duration_s REAL NOT NULL, sample_rate INTEGER NOT NULL,
        channels INTEGER NOT NULL, bytes INTEGER NOT NULL, relative_path TEXT NOT NULL,
        transcript TEXT, consent_version TEXT NOT NULL, consent_timestamp TEXT NOT NULL,
        license_scope TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(sha256, speaker_id))""")
    conn.commit()
    return conn


def ingest(root: Path, audio: bytes, speaker_id: str, consent: bool,
           consent_version: str = "v1", license_scope: str = "research_internal",
           transcript: str | None = None) -> dict:
    if not consent:
        raise ValueError("Explicit informed consent is required")
    if not speaker_id.strip() or len(speaker_id) > 128:
        raise ValueError("Provide a pseudonymous speaker_id (1–128 chars)")
    if license_scope not in {"research_internal", "dataset_release_approved"}:
        raise ValueError("Unsupported license scope")
    if not audio or len(audio) > MAX_BYTES:
        raise ValueError("WAV must be nonempty and <=20 MB")
    try:
        with wave.open(io.BytesIO(audio), "rb") as wav:
            if wav.getcomptype() != "NONE":
                raise ValueError("Uncompressed PCM WAV required")
            rate = wav.getframerate()
            channels = wav.getnchannels()
            frames = wav.getnframes()
            width = wav.getsampwidth()
    except (wave.Error, EOFError) as exc:
        raise ValueError("Invalid PCM WAV") from exc
    if rate not in {8000, 16000, 22050, 44100, 48000} or channels not in {1, 2} or width not in {1, 2, 3, 4}:
        raise ValueError("Unsupported audio format")
    duration = frames / rate
    if not 0.3 <= duration <= 120:
        raise ValueError("Duration outside accepted range")
    digest = hashlib.sha256(audio).hexdigest()
    conn = init_db(root)
    try:
        existing = conn.execute("SELECT id FROM recordings WHERE sha256=? AND speaker_id=?", (digest, speaker_id)).fetchone()
        if existing:
            return {"id": existing[0], "duplicate": True, "sha256": digest}
        uid = uuid.uuid4().hex
        relative = f"private_audio/{uid}.wav"
        (root / "private_audio").mkdir(exist_ok=True)
        target = root / relative
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(audio)
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("INSERT INTO recordings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (uid, digest, speaker_id, "fon", duration, rate, channels, len(audio), relative,
                          transcript, consent_version, now, license_scope, "pending_review", now))
            conn.commit()
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return {"id": uid, "duplicate": False, "sha256": digest,
                "duration_s": round(duration, 3), "status": "pending_review"}
    finally:
        conn.close()


def manifest(root: Path, approved_only: bool = True) -> list[dict]:
    conn = init_db(root)
    try:
        where = "WHERE status='approved' AND transcript IS NOT NULL" if approved_only else ""
        rows = conn.execute(f"SELECT id,relative_path,speaker_id,language,duration_s,sample_rate,transcript,status,license_scope FROM recordings {where} ORDER BY id").fetchall()
        keys = ("id", "audio", "speaker_id", "language", "duration_s", "sample_rate", "text", "status", "license_scope")
        return [dict(zip(keys, row)) for row in rows]
    finally:
        conn.close()


def export_manifest(root: Path, output: Path) -> int:
    rows = manifest(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)
