from conftest import login_admin
import sqlite3

import pytest
from fastapi.testclient import TestClient

from beninspeechlab.api import app
from beninspeechlab.core import ingest, init_db, list_recordings
from test_pipeline import wav_bytes


def test_migrates_existing_database(tmp_path):
    database = tmp_path / "metadata.sqlite3"
    conn = sqlite3.connect(database)
    conn.execute("""CREATE TABLE recordings (
        id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, speaker_id TEXT NOT NULL,
        language TEXT NOT NULL, duration_s REAL NOT NULL, sample_rate INTEGER NOT NULL,
        channels INTEGER NOT NULL, bytes INTEGER NOT NULL, relative_path TEXT NOT NULL,
        transcript TEXT, consent_version TEXT NOT NULL, consent_timestamp TEXT NOT NULL,
        license_scope TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(sha256, speaker_id))""")
    conn.commit()
    conn.close()
    migrated = init_db(tmp_path)
    columns = {row[1] for row in migrated.execute("PRAGMA table_info(recordings)")}
    migrated.close()
    assert {"age_group", "linguistic_region", "fon_variant"} <= columns
    assert list_recordings(tmp_path) == []


def test_speaker_profile_saved_and_listed(tmp_path, monkeypatch):
    monkeypatch.setenv("BENINSPEECH_DATA", str(tmp_path))
    result = ingest(tmp_path, wav_bytes(), "speaker-a", True,
                    age_group="25-34", linguistic_region="Abomey",
                    fon_variant="Fon déclaré")
    assert not result["duplicate"]
    item = list_recordings(tmp_path)[0]
    assert item["age_group"] == "25-34"
    assert item["linguistic_region"] == "Abomey"
    assert item["fon_variant"] == "Fon déclaré"
    client = TestClient(app)
    login_admin(client)
    response = client.get("/v1/recordings")
    assert response.status_code == 200
    assert response.json()[0]["age_group"] == "25-34"


def test_invalid_or_conflicting_profile(tmp_path):
    with pytest.raises(ValueError, match="age group"):
        ingest(tmp_path, wav_bytes(), "speaker-a", True, age_group="under-18")
    ingest(tmp_path, wav_bytes(), "speaker-a", True, age_group="25-34")
    with pytest.raises(ValueError, match="Conflicting"):
        ingest(tmp_path, wav_bytes(seconds=2), "speaker-a", True,
               age_group="35-44")
