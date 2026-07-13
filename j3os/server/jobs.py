"""Thread-based job manager for live pipeline runs.

Each run executes ``run_pipeline`` in a daemon thread; progress events
are appended to the job's event log and consumers (SSE streams) block on
a condition variable until new events arrive. Every job ends with exactly
one ``job_done`` event.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterator

from j3os.core.brand import Brand
from j3os.engines.editorial.pipeline import STAGE_KEYS, run_pipeline


@dataclass
class Job:
    id: str
    brand: str
    topic: str
    stages: list[str] | None
    dry_run: bool
    status: str = "running"  # running | completed | failed
    error: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    events: list[dict] = field(default_factory=list)
    cond: threading.Condition = field(default_factory=threading.Condition)

    def append_event(self, event: dict) -> None:
        with self.cond:
            event = dict(event)
            event["seq"] = len(self.events)
            self.events.append(event)
            self.cond.notify_all()

    def summary(self) -> dict:
        return {
            "id": self.id,
            "brand": self.brand,
            "topic": self.topic,
            "stages": self.stages,
            "dry_run": self.dry_run,
            "status": self.status,
            "error": self.error,
            "created_at": self.created_at,
            "events_count": len(self.events),
        }


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def start(
        self,
        brand_slug: str,
        topic: str,
        stages: list[str] | None = None,
        dry_run: bool = True,
    ) -> Job:
        brand = Brand.load(brand_slug)  # raises FileNotFoundError for unknown brand
        unknown = set(stages or []) - set(STAGE_KEYS)
        if unknown:
            raise ValueError(f"Unknown stages: {sorted(unknown)}. Valid: {STAGE_KEYS}")
        job = Job(
            id=uuid.uuid4().hex[:12],
            brand=brand_slug,
            topic=topic,
            stages=stages,
            dry_run=dry_run,
        )
        with self._lock:
            self._jobs[job.id] = job

        def worker() -> None:
            try:
                run_pipeline(
                    brand,
                    topic,
                    stages=stages,
                    dry_run=dry_run,
                    progress=job.append_event,
                )
            except Exception as exc:  # surface any failure to the stream
                job.status = "failed"
                job.error = str(exc)
                job.append_event(
                    {"event": "job_done", "status": "failed", "error": str(exc)}
                )
            else:
                job.status = "completed"
                job.append_event({"event": "job_done", "status": "completed"})

        threading.Thread(target=worker, daemon=True, name=f"j3os-run-{job.id}").start()
        return job

    def get(self, job_id: str) -> Job:
        with self._lock:
            return self._jobs[job_id]  # KeyError for unknown job

    def list_jobs(self) -> list[dict]:
        with self._lock:
            jobs = list(self._jobs.values())
        return [j.summary() for j in sorted(jobs, key=lambda j: j.created_at, reverse=True)]

    def iter_events(self, job_id: str, start: int = 0) -> Iterator[dict]:
        """Yield events from ``start`` onward, blocking until the job ends."""
        job = self.get(job_id)
        index = start
        while True:
            with job.cond:
                while index >= len(job.events):
                    job.cond.wait(timeout=1.0)
            while index < len(job.events):
                event = job.events[index]
                index += 1
                yield event
                if event.get("event") == "job_done":
                    return
