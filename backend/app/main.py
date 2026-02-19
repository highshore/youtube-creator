from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from .config import SETTINGS
from .job_store import JobStore
from .logging_setup import configure_logging
from .models import JobCreateRequest, JobDetail, JobSummary, LibraryItem, ReviewRequest
from .system import check_media_dependencies

configure_logging(SETTINGS.logs_root)

app = FastAPI(title="YouTube Shorts Multi-Agent API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=SETTINGS.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/media", StaticFiles(directory=str(SETTINGS.data_root)), name="media")

store = JobStore()
dependency_snapshot = check_media_dependencies()
if dependency_snapshot["overall"] == "fail":
    logger.error("Critical media dependencies missing: {}", dependency_snapshot)
elif dependency_snapshot["overall"] == "warn":
    logger.warning("Optional media dependencies missing: {}", dependency_snapshot)
else:
    logger.info("Media dependency check passed.")


def _path_to_media_url(local_path: str | None) -> str | None:
    if not local_path:
        return None
    p = Path(local_path).resolve()
    try:
        rel = p.relative_to(SETTINGS.data_root.resolve())
    except ValueError:
        return None
    return f"/media/{rel.as_posix()}"


def _serialize_state(state: dict) -> dict:
    out = dict(state)
    for key in ["final_video", "audio_narration", "bg_music", "metadata_path"]:
        if key in out:
            out[f"{key}_url"] = _path_to_media_url(out.get(key))
    out["clips_urls"] = [_path_to_media_url(p) for p in out.get("clips", [])]
    out["images_urls"] = [_path_to_media_url(p) for p in out.get("images", [])]
    return out


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "time": datetime.utcnow().isoformat() + "Z"}


@app.get("/api/system/dependencies")
def system_dependencies() -> dict:
    return check_media_dependencies()


@app.post("/api/jobs", response_model=JobSummary)
def create_job(payload: JobCreateRequest) -> JobSummary:
    topic = payload.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic must not be empty")
    record = store.create_job(topic)
    store.start_job(record.job_id)
    return JobSummary(
        job_id=record.job_id,
        topic=record.topic,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@app.get("/api/jobs", response_model=list[JobSummary])
def list_jobs() -> list[JobSummary]:
    rows = store.list_jobs()
    return [
        JobSummary(
            job_id=r.job_id,
            topic=r.topic,
            status=r.status,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@app.get("/api/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: str) -> JobDetail:
    record = store.get_job(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="job not found")
    return JobDetail(
        job_id=record.job_id,
        thread_id=record.thread_id,
        topic=record.topic,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
        review_payload=record.review_payload,
        state=_serialize_state(record.state),
        error=record.error,
    )


@app.post("/api/jobs/{job_id}/review", response_model=JobSummary)
def review_job(job_id: str, payload: ReviewRequest) -> JobSummary:
    review_payload = {
        "human_decision": payload.human_decision,
        "review_notes": payload.review_notes.strip(),
    }
    try:
        store.resume_job(job_id, review_payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record = store.get_job(job_id)
    assert record is not None
    return JobSummary(
        job_id=record.job_id,
        topic=record.topic,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@app.get("/api/library", response_model=list[LibraryItem])
def list_library() -> list[LibraryItem]:
    output_dir = SETTINGS.output_root
    rows: list[LibraryItem] = []
    if not output_dir.exists():
        return rows

    metadata_files = sorted(output_dir.glob("short_metadata_*.json"), reverse=True)
    for meta_path in metadata_files[:100]:
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to parse metadata file {}: {}", meta_path, exc)
            continue

        created_at = datetime.fromtimestamp(meta_path.stat().st_mtime)
        final_video = payload.get("final_video")
        rows.append(
            LibraryItem(
                job_id=payload.get("job_id"),
                topic=payload.get("topic"),
                script=payload.get("script"),
                final_video=final_video,
                final_video_url=_path_to_media_url(final_video),
                metadata_path=str(meta_path),
                created_at=created_at,
            )
        )
    return rows


def run() -> None:
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()
