import os
import time
import uuid
import tempfile

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel

from app.models.schemas import DetectionResult, confidence_bucket
from app.services.video_detection import analyze_video, extract_first_frame
from app.services import cache
from app.services import scans as scans_service
from app.services import thumbnails
from app.routers.auth import get_current_user

router = APIRouter()

MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100MB
ALLOWED_CONTENT_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"}
JOB_TTL_SECONDS = 60 * 60

_jobs: dict[str, dict] = {}


class VideoJobResponse(BaseModel):
    job_id: str
    status: str


def _sweep_stale_jobs():
    now = time.monotonic()
    stale = [
        job_id
        for job_id, job in _jobs.items()
        if now - job.get("created_at", now) > JOB_TTL_SECONDS
    ]
    for job_id in stale:
        _jobs.pop(job_id, None)


def _process_video_job(job_id: str, video_path: str, cache_key: str, user_id: int, label: str):
    try:
        def on_progress(done: int, total: int):
            _jobs[job_id]["progress"] = {"frames_done": done, "frames_total": total}

        thumbnail_holder: dict[str, str] = {}

        def on_first_frame(frame):
            thumbnail_holder["thumbnail"] = thumbnails.make_thumbnail_data_url(frame)

        result = analyze_video(
            video_path, progress_callback=on_progress, on_first_frame=on_first_frame
        )

        response = DetectionResult(
            media_type="video",
            ai_probability=result["ai_probability"],
            confidence=confidence_bucket(result["ai_probability"]),
            components=result["components"],
            risk_flags=result["risk_flags"],
        ).model_dump()

        cache.set(cache_key, response)
        scan_id = scans_service.save_scan(
            user_id, "video", label, response, thumbnail=thumbnail_holder.get("thumbnail")
        )
        response["id"] = scan_id

        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["result"] = response
    except Exception as exc:
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = str(exc)
    finally:
        if os.path.exists(video_path):
            os.remove(video_path)


def _thumbnail_from_bytes(video_bytes: bytes, filename: str | None) -> str | None:
    """Used only on the cache-hit shortcut, where the full frame-sampling
    pass in analyze_video() never runs - grabs just one frame cheaply."""
    suffix = os.path.splitext(filename or "")[1] or ".mp4"
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp_file.write(video_bytes)
        tmp_file.close()
        frame = extract_first_frame(tmp_file.name)
        return thumbnails.make_thumbnail_data_url(frame) if frame else None
    finally:
        if os.path.exists(tmp_file.name):
            os.remove(tmp_file.name)


@router.post("/video", response_model=VideoJobResponse)
async def analyze_video_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}",
        )

    video_bytes = await file.read()

    if len(video_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size is {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.",
        )

    if not video_bytes:
        raise HTTPException(status_code=400, detail="Empty file.")

    _sweep_stale_jobs()

    label = file.filename or "Uploaded video"

    cache_key = cache.make_key(video_bytes)
    cached = cache.get(cache_key)
    if cached:
        job_id = str(uuid.uuid4())
        _jobs[job_id] = {
            "status": "done",
            "result": cached,
            "progress": {"frames_done": 0, "frames_total": 0},
            "created_at": time.monotonic(),
        }
        thumbnail = _thumbnail_from_bytes(video_bytes, file.filename)
        scan_id = scans_service.save_scan(user["id"], "video", label, cached, thumbnail=thumbnail)
        _jobs[job_id]["result"] = {**cached, "id": scan_id}
        return VideoJobResponse(job_id=job_id, status="done")

    job_id = str(uuid.uuid4())
    suffix = os.path.splitext(file.filename or "")[1] or ".mp4"
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_file.write(video_bytes)
    tmp_file.close()

    _jobs[job_id] = {
        "status": "processing",
        "progress": {"frames_done": 0, "frames_total": None},
        "created_at": time.monotonic(),
    }
    background_tasks.add_task(
        _process_video_job, job_id, tmp_file.name, cache_key, user["id"], label
    )

    return VideoJobResponse(job_id=job_id, status="processing")


@router.get("/video/{job_id}")
def get_video_job_status(job_id: str, user: dict = Depends(get_current_user)):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job
