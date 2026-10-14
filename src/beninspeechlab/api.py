import os
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from .core import ingest, MAX_BYTES, list_recordings, get_recording_audio, review_recording, corpus_stats

app = FastAPI(title="BeninSpeechLab · Fon Speech Ingestion", version="0.1.0")

@app.get("/studio", response_class=HTMLResponse, include_in_schema=False)
def studio():
    return (Path(__file__).parent / "studio.html").read_text(encoding="utf-8")

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


class ReviewPayload(BaseModel):
    transcript: str = ""
    status: str = "pending_review"


def local_only(request: Request):
    # No authentication exists yet. Never make private audio endpoints public.
    if not request.client or request.client.host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        raise HTTPException(403, "Private research endpoints are local-only")


@app.get("/v1/recordings")
def recordings(request: Request):
    local_only(request)
    return list_recordings(Path(os.environ.get("BENINSPEECH_DATA", "./data")))


@app.get("/v1/recordings/{recording_id}/audio")
def recording_audio(recording_id: str, request: Request):
    local_only(request)
    path = get_recording_audio(Path(os.environ.get("BENINSPEECH_DATA", "./data")), recording_id)
    if path is None:
        raise HTTPException(404, "Recording not found")
    return FileResponse(path, media_type="audio/wav", filename="recording.wav")


@app.patch("/v1/recordings/{recording_id}/review")
def recording_review(recording_id: str, payload: ReviewPayload, request: Request):
    local_only(request)
    try:
        result = review_recording(
            Path(os.environ.get("BENINSPEECH_DATA", "./data")),
            recording_id, payload.transcript, payload.status
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if result is None:
        raise HTTPException(404, "Recording not found")
    return result


@app.get("/v1/stats")
def stats(request: Request):
    local_only(request)
    return corpus_stats(Path(os.environ.get("BENINSPEECH_DATA", "./data")))
