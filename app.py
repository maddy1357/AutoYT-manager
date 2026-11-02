"""AutoYT-manager web app. Run: python app.py  (then open http://127.0.0.1:8000)"""
import shutil
import threading
import uuid
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from autoyt import ai, pipeline, youtube
from autoyt.config import CLIENT_SECRET_FILE, ROOT, UPLOAD_DIR, provider_configured

app = FastAPI(title="AutoYT-manager")
ALLOWED_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}
PRIVACY = {"private", "unlisted", "public"}
_connect_state = {"running": False, "error": None}


def _job_view(job: pipeline.Job) -> dict:
    d = asdict(job)
    d.pop("source", None)
    d["full_description"] = pipeline.full_description(job) if job.metadata else ""
    d["urls"] = {k: f"/files/{job.id}/{v}" for k, v in job.files.items()}
    d["file_base"] = f"/files/{job.id}/"
    if job.suggestions:
        d["default_choices"] = job.choices or pipeline.default_choices(job)
    return d


def _options(privacy: str, music_mood: str, replace_audio: bool, title_card: bool, auto_upload: bool,
             made_for_kids: bool, synthetic_media: bool, ai_provider: str,
             target_seconds: int = 60) -> pipeline.Options:
    if privacy not in PRIVACY:
        raise HTTPException(400, "privacy must be private, unlisted or public")
    ai_provider = ai_provider or ai.default_provider()
    if ai_provider not in ai.PROVIDERS:
        raise HTTPException(400, f"Unknown AI provider '{ai_provider}'")
    if not provider_configured(ai_provider):
        info = ai.PROVIDERS[ai_provider]
        raise HTTPException(400, f"{info['label']} has no API key. Add {info['key']} to .env and restart the app.")
    return pipeline.Options(privacy=privacy, music_mood=music_mood, replace_audio=replace_audio,
                            title_card=title_card, auto_upload=auto_upload, made_for_kids=made_for_kids,
                            synthetic_media=synthetic_media, target_seconds=max(20, min(600, target_seconds)),
                            ai_provider=ai_provider)


@app.get("/", response_class=HTMLResponse)
def index():
    return (ROOT / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/status")
def status():
    channel, yt_error = None, None
    try:
        channel = youtube.channel_info()
    except Exception as e:
        yt_error = str(e)
    return {
        "providers": [
            {"id": pid, "label": p["label"], "model": p["model"], "free": p["free"], "key": p["key"],
             "configured": provider_configured(pid)}
            for pid, p in ai.PROVIDERS.items()
        ],
        "default_provider": ai.default_provider(),
        "client_secret_present": CLIENT_SECRET_FILE.exists(),
        "youtube_channel": channel,
        "youtube_error": yt_error or _connect_state["error"],
        "connecting": _connect_state["running"],
    }


@app.post("/api/youtube/connect")
def youtube_connect():
    if _connect_state["running"]:
        return {"started": False}
    if not CLIENT_SECRET_FILE.exists():
        raise HTTPException(400, "client_secret.json not found. See README: 'Connect your YouTube channel'.")

    def run():
        _connect_state.update(running=True, error=None)
        try:
            youtube.get_credentials(interactive=True)
        except Exception as e:
            _connect_state["error"] = str(e)
        finally:
            _connect_state["running"] = False
    threading.Thread(target=run, daemon=True).start()
    return {"started": True}


@app.post("/api/youtube/disconnect")
def youtube_disconnect():
    youtube.disconnect()
    return {"ok": True}


@app.post("/api/jobs/video")
async def new_video_job(
    file: UploadFile = File(...), notes: str = Form(""), privacy: str = Form("private"),
    music_mood: str = Form("auto"), replace_audio: bool = Form(False), title_card: bool = Form(True),
    auto_upload: bool = Form(False), made_for_kids: bool = Form(False), synthetic_media: bool = Form(False),
    ai_provider: str = Form(""), ai_decides: bool = Form(False),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Unsupported file type {ext or '(none)'}. Use: {', '.join(sorted(ALLOWED_EXT))}")
    opts = _options(privacy, music_mood, replace_audio, title_card, auto_upload, made_for_kids, synthetic_media,
                    ai_provider)
    opts.ai_decides = ai_decides
    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f, length=4 * 1024 * 1024)
    return _job_view(pipeline.create_job("video", opts, prompt=notes, source=dest))


@app.post("/api/jobs/prompt")
def new_prompt_job(
    prompt: str = Form(...), privacy: str = Form("private"), music_mood: str = Form("auto"),
    target_seconds: int = Form(60), auto_upload: bool = Form(False), made_for_kids: bool = Form(False),
    synthetic_media: bool = Form(False), ai_provider: str = Form(""),
):
    if len(prompt.strip()) < 5:
        raise HTTPException(400, "Describe the video you want in a sentence or more.")
    opts = _options(privacy, music_mood, False, False, auto_upload, made_for_kids, synthetic_media, ai_provider,
                    target_seconds)
    return _job_view(pipeline.create_job("prompt", opts, prompt=prompt))


@app.get("/api/jobs")
def jobs():
    return [_job_view(j) for j in pipeline.list_jobs()]


def _get(job_id: str) -> pipeline.Job:
    job = pipeline.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: str):
    return _job_view(_get(job_id))


class MetadataPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    hashtags: list[str] | None = None
    tags: list[str] | None = None
    thumbnail_text: str | None = None
    privacy: str | None = None


@app.patch("/api/jobs/{job_id}")
def edit_job(job_id: str, patch: MetadataPatch):
    job = _get(job_id)
    if job.status in ("processing", "queued", "uploading"):
        raise HTTPException(409, "Wait until processing finishes.")
    changes = patch.model_dump(exclude_none=True)
    if (p := changes.pop("privacy", None)) is not None:
        if p not in PRIVACY:
            raise HTTPException(400, "Invalid privacy value")
        job.options.privacy = p
    pipeline.update_metadata(job, changes)
    return _job_view(job)


class Choices(BaseModel):
    title: str
    description: str
    hashtags: list[str] = []
    tags: list[str] = []
    category_id: str | None = None
    thumbnail_index: int = 0
    thumbnail_text: str = ""
    music_mood: str = "none"
    replace_audio: bool = False
    title_card: bool = True
    privacy: str = "private"
    made_for_kids: bool = False
    synthetic_media: bool = False
    auto_upload: bool = True
    confirm_rights: bool = False


@app.post("/api/jobs/{job_id}/finalize")
def finalize_job(job_id: str, choices: Choices):
    job = _get(job_id)
    if job.mode != "video" or not job.suggestions:
        raise HTTPException(409, "This job has no suggestions to choose from.")
    if job.status in ("queued", "processing", "uploading"):
        raise HTTPException(409, "Wait until the current step finishes.")
    if job.status == "uploaded":
        raise HTTPException(409, "This video is already on YouTube. Edit it in YouTube Studio.")
    if choices.auto_upload and youtube.get_credentials() is None:
        raise HTTPException(400, "Connect your YouTube channel first, or untick 'Upload to YouTube when done'.")
    if not choices.title.strip():
        raise HTTPException(400, "Title cannot be empty.")
    pipeline.finalize(job, choices.model_dump())
    return _job_view(job)


class UploadRequest(BaseModel):
    confirm_rights: bool = False


@app.post("/api/jobs/{job_id}/upload")
def upload_job(job_id: str, req: UploadRequest):
    job = _get(job_id)
    if youtube.get_credentials() is None:
        raise HTTPException(400, "Connect your YouTube channel first.")
    if job.status not in ("ready", "needs_review", "failed") or "video" not in job.files:
        raise HTTPException(409, "This video is not ready to upload.")
    try:
        pipeline.upload_async(job, override_review=req.confirm_rights)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    return {"started": True}


@app.post("/api/jobs/{job_id}/retry")
def retry_job(job_id: str):
    job = _get(job_id)
    if job.status != "failed":
        raise HTTPException(409, "Only failed jobs can be retried.")
    if job.mode == "video" and not (job.source and Path(job.source).exists()):
        raise HTTPException(410, "The original upload is gone; start a new job.")
    if job.youtube.get("video_id") is None and "video" in job.files and job.metadata and job.step.startswith("Uploading"):
        pipeline.upload_async(job, override_review=True)  # failed during upload: retry just the upload
    else:
        pipeline.start(job)
    return {"started": True}


@app.get("/files/{job_id}/{name:path}")
def job_file(job_id: str, name: str):
    job = _get(job_id)
    path = (job.dir / name).resolve()
    if not path.is_relative_to(job.dir.resolve()) or not path.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(path)


if __name__ == "__main__":
    import webbrowser

    import uvicorn

    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:8000")).start()
    uvicorn.run(app, host="127.0.0.1", port=8000)
