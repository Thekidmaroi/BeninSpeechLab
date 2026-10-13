import os
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from .core import ingest, MAX_BYTES

app = FastAPI(title="BeninSpeechLab · Fon Speech Ingestion", version="0.1.0")

@app.get("/health")
def health():
    return {"status": "ok", "pilot_language": "fon"}

@app.post("/v1/recordings", status_code=201)
async def create_recording(
    file: UploadFile = File(...),
    speaker_id: str = Form(...),
    consent: bool = Form(...),
    consent_version: str = Form("v1"),
    license_scope: str = Form("research_internal"),
    transcript: str | None = Form(None),
):
    if not (file.filename or "").lower().endswith(".wav"):
        raise HTTPException(422, "Only PCM WAV is supported in the MVP")
    content = await file.read(MAX_BYTES + 1)
    try:
        return ingest(Path(os.environ.get("BENINSPEECH_DATA", "./data")), content,
                      speaker_id, consent, consent_version, license_scope, transcript)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
