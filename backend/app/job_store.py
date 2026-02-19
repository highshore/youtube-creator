from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langgraph.types import Command
from loguru import logger

from .config import SETTINGS
from .pipeline import ShortState, build_graph
from .pipeline.retry import retry_call
from .pipeline.utils import ensure_dir


@dataclass
class JobRecord:
    job_id: str
    thread_id: str
    topic: str
    status: str
    created_at: datetime
    updated_at: datetime
    state: dict[str, Any] = field(default_factory=dict)
    review_payload: dict[str, Any] | None = None
    error: str | None = None


class JobStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._jobs: dict[str, JobRecord] = {}
        self._graph = build_graph()
        self._jobs_dir = ensure_dir(SETTINGS.data_root / "jobs")
        self._load_jobs_from_disk()

    def create_job(self, topic: str) -> JobRecord:
        now = datetime.now(timezone.utc)
        job_id = f"job-{uuid.uuid4().hex[:10]}"
        record = JobRecord(
            job_id=job_id,
            thread_id=f"thread-{job_id}",
            topic=topic,
            status="queued",
            created_at=now,
            updated_at=now,
            state={
                "job_id": job_id,
                "topic": topic,
                "status": "queued",
                "clips": [],
                "images": [],
                "attribution": [],
                "errors": [],
                "max_asset_attempts": 3,
                "assets_dir": str(SETTINGS.assets_root),
                "output_dir": str(SETTINGS.output_root),
            },
        )
        with self._lock:
            self._jobs[job_id] = record
        self._persist(record)
        return record

    def start_job(self, job_id: str) -> None:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(job_id)
            self._jobs[job_id].status = "running"
            self._jobs[job_id].updated_at = datetime.now(timezone.utc)
        self._spawn(job_id, resume_payload=None)

    def resume_job(self, job_id: str, review_payload: dict[str, Any]) -> None:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(job_id)
            record = self._jobs[job_id]
            if record.status != "waiting_review":
                raise ValueError(f"job {job_id} is not waiting_review.")
            record.status = "running"
            record.review_payload = None
            record.updated_at = datetime.now(timezone.utc)
        self._spawn(job_id, resume_payload=review_payload)

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._lock:
            record = self._jobs.get(job_id)
            if not record:
                return None
            return JobRecord(**asdict(record))

    def list_jobs(self) -> list[JobRecord]:
        with self._lock:
            rows = [JobRecord(**asdict(r)) for r in self._jobs.values()]
        return sorted(rows, key=lambda r: r.created_at, reverse=True)

    def _load_jobs_from_disk(self) -> None:
        files = sorted(self._jobs_dir.glob("job-*.json"))
        if not files:
            return
        restored = 0
        for file_path in files:
            try:
                raw = json.loads(file_path.read_text(encoding="utf-8"))
                status = str(raw.get("status", "failed"))
                state = dict(raw.get("state", {}))
                # A previously running in-memory worker is gone after restart.
                if status == "running":
                    status = "failed"
                    errors = list(state.get("errors", []))
                    errors.append("interrupted by server restart")
                    state["errors"] = errors
                    state["status"] = "failed:interrupted"
                    state["next_action"] = "failed"

                record = JobRecord(
                    job_id=str(raw["job_id"]),
                    thread_id=str(raw.get("thread_id", f"thread-{raw['job_id']}")),
                    topic=str(raw.get("topic", "")),
                    status=status,
                    created_at=datetime.fromisoformat(raw["created_at"]),
                    updated_at=datetime.fromisoformat(raw["updated_at"]),
                    state=state,
                    review_payload=raw.get("review_payload"),
                    error=raw.get("error"),
                )
                self._jobs[record.job_id] = record
                restored += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to restore job file {}: {}", file_path, exc)
        if restored:
            logger.info("Restored {} jobs from disk.", restored)

    def _spawn(self, job_id: str, resume_payload: dict[str, Any] | None) -> None:
        t = threading.Thread(
            target=self._run_job,
            args=(job_id, resume_payload),
            daemon=True,
            name=f"worker-{job_id}",
        )
        t.start()

    def _run_job(self, job_id: str, resume_payload: dict[str, Any] | None) -> None:
        with self._lock:
            record = self._jobs.get(job_id)
            if not record:
                return
            state = dict(record.state)
            config = {"configurable": {"thread_id": record.thread_id}}

        try:
            logger.info("Running job {} (resume={})", job_id, bool(resume_payload))
            if resume_payload is None:
                result = retry_call(
                    f"graph_invoke:{job_id}",
                    lambda: self._graph.invoke(state, config=config),
                    max_attempts=2,
                )
            else:
                result = retry_call(
                    f"graph_resume:{job_id}",
                    lambda: self._graph.invoke(Command(resume=resume_payload), config=config),
                    max_attempts=2,
                )

            with self._lock:
                record = self._jobs[job_id]
                cleaned = dict(result)
                cleaned.pop("__interrupt__", None)
                record.state = cleaned
                record.updated_at = datetime.now(timezone.utc)

                if "__interrupt__" in result:
                    record.review_payload = self._extract_interrupt_payload(result)
                    record.status = "waiting_review"
                else:
                    next_action = str(result.get("next_action", ""))
                    status = str(result.get("status", ""))
                    if next_action == "complete" or status == "completed":
                        record.status = "completed"
                    elif next_action == "failed" or status.startswith("failed"):
                        record.status = "failed"
                    else:
                        record.status = "running"
                record.error = None
                self._persist(record)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Job {} crashed", job_id)
            with self._lock:
                record = self._jobs[job_id]
                record.status = "failed"
                record.error = str(exc)
                record.updated_at = datetime.now(timezone.utc)
                state = dict(record.state)
                errors = list(state.get("errors", []))
                errors.append(f"job_store runner error: {exc}")
                state["errors"] = errors
                state["status"] = "failed:runner"
                state["next_action"] = "failed"
                record.state = state
                self._persist(record)

    @staticmethod
    def _extract_interrupt_payload(result: dict[str, Any]) -> dict[str, Any]:
        interrupts = result.get("__interrupt__", [])
        if not interrupts:
            return {}
        first = interrupts[0]
        value = getattr(first, "value", first)
        if isinstance(value, dict):
            return value
        return {"message": str(value)}

    def _persist(self, record: JobRecord) -> None:
        path = self._jobs_dir / f"{record.job_id}.json"
        payload = {
            "job_id": record.job_id,
            "thread_id": record.thread_id,
            "topic": record.topic,
            "status": record.status,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "review_payload": record.review_payload,
            "error": record.error,
            "state": record.state,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
