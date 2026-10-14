import os
import tempfile
from fastapi import BackgroundTasks
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from pydantic import BaseModel
from .security import COOKIE, SESSION_SECONDS, check_password, configured, csrf_token, issue_session, require_admin, same_origin, secure_transport
from .core import ingest, MAX_BYTES, list_recordings, get_recording_audio, review_recording, corpus_stats, build_asr_export

app = FastAPI(title="BeninSpeechLab · Fon Speech Ingestion", version="0.1.0")

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
        "connect-src 'self'; media-src 'self' blob:; img-src 'self' blob:; "
        "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
    )
    return response


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("/contribute", status_code=302)


@app.get("/contribute", response_class=HTMLResponse, include_in_schema=False)
def contribute():
    return (Path(__file__).parent / "contribute.html").read_text(encoding="utf-8")


@app.get("/admin/login", response_class=HTMLResponse, include_in_schema=False)
def admin_login_page():
    return (Path(__file__).parent / "login.html").read_text(encoding="utf-8")


@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
def admin_page(request: Request):
    require_admin(request)
    return (Path(__file__).parent / "studio.html").read_text(encoding="utf-8")


@app.get("/studio", include_in_schema=False)
def legacy_studio():
    return RedirectResponse("/admin", status_code=302)


class LoginPayload(BaseModel):
    password: str


@app.post("/v1/admin/login")
def admin_login(payload: LoginPayload, request: Request):
    secure_transport(request)
    same_origin(request)
    client_key = request.client.host if request.client else "unknown"
    check_password(payload.password, client_key)
    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(COOKIE, issue_session(), max_age=SESSION_SECONDS,
                        httponly=True, secure=request.url.scheme == "https",
                        samesite="strict", path="/")
    return response


@app.get("/v1/admin/session")
def admin_session(request: Request):
    return {"csrf_token": csrf_token(request)}


@app.post("/v1/admin/logout")
def admin_logout(request: Request):
    require_admin(request, mutation=True)
    response = RedirectResponse("/admin/login", status_code=303)
    response.delete_cookie(COOKIE, path="/")
    return response

@app.get("/health")
def health():
    return {"status": "ok", "pilot_language": "fon"}

@app.post("/v1/recordings", status_code=201)
async def create_recording(
    request: Request,
    file: UploadFile = File(...),
    speaker_id: str = Form(...),
    consent: bool = Form(...),
    consent_version: str = Form("v1"),
    license_scope: str = Form("research_internal"),
    transcript: str | None = Form(None),
    age_group: str | None = Form(None),
    linguistic_region: str | None = Form(None),
    fon_variant: str | None = Form(None),
):
    secure_transport(request)
    same_origin(request)
    if not (file.filename or "").lower().endswith(".wav"):
        raise HTTPException(422, "Only PCM WAV is supported in the MVP")
    content = await file.read(MAX_BYTES + 1)
    try:
        return ingest(Path(os.environ.get("BENINSPEECH_DATA", "./data")), content,
                      speaker_id, consent, consent_version, license_scope, transcript,
                      age_group, linguistic_region, fon_variant)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


class ReviewPayload(BaseModel):
    transcript: str = ""
    status: str = "pending_review"




@app.get("/v1/recordings")
def recordings(request: Request):
    require_admin(request)
    return list_recordings(Path(os.environ.get("BENINSPEECH_DATA", "./data")))


@app.get("/v1/recordings/{recording_id}/audio")
def recording_audio(recording_id: str, request: Request):
    require_admin(request)
    path = get_recording_audio(Path(os.environ.get("BENINSPEECH_DATA", "./data")), recording_id)
    if path is None:
        raise HTTPException(404, "Recording not found")
    return FileResponse(path, media_type="audio/wav", filename="recording.wav")


@app.patch("/v1/recordings/{recording_id}/review")
def recording_review(recording_id: str, payload: ReviewPayload, request: Request):
    require_admin(request, mutation=True)
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
    require_admin(request)
    return corpus_stats(Path(os.environ.get("BENINSPEECH_DATA", "./data")))


@app.get("/v1/export/asr")
def export_asr(request: Request, background_tasks: BackgroundTasks):
    require_admin(request)
    # Create a temporary ZIP and delete it after FileResponse completes.
    import os as _os
    fd, name = tempfile.mkstemp(prefix="beninspeechlab_asr_", suffix=".zip")
    _os.close(fd)
    archive = Path(name)
    try:
        build_asr_export(Path(os.environ.get("BENINSPEECH_DATA", "./data")), archive)
    except ValueError as exc:
        archive.unlink(missing_ok=True)
        raise HTTPException(422, str(exc)) from exc
    except Exception:
        archive.unlink(missing_ok=True)
        raise
    background_tasks.add_task(archive.unlink, missing_ok=True)
    return FileResponse(archive, media_type="application/zip",
                        filename="beninspeechlab_fon_asr.zip",
                        background=background_tasks)
