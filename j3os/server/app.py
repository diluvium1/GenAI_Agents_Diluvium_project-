"""J3OS live console server.

Run with ``python -m j3os serve`` and open http://127.0.0.1:8300 — the
console runs the editorial pipeline for real (or in dry-run mode when no
``ANTHROPIC_API_KEY`` is set) and streams every stage's output to the
browser over Server-Sent Events.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel

import j3os
from j3os.core.brand import Brand, discover_brands
from j3os.core.engine import default_registry
from j3os.engines.editorial.pipeline import PIPELINE
from j3os.engines.knowledge.engine import KnowledgeEngine
from j3os.server.jobs import JobManager

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="J3OS Console", version=j3os.__version__)
manager = JobManager()


def _live_capable() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


class RunRequest(BaseModel):
    brand: str
    topic: str
    stages: list[str] | None = None
    dry_run: bool | None = None
    web_research: bool = False
    orchestrate: bool = False


@app.get("/")
def index():
    page = STATIC_DIR / "index.html"
    if page.exists():
        return FileResponse(page)
    return PlainTextResponse("J3OS console UI not built yet")


@app.get("/api/status")
def status():
    return {
        "version": j3os.__version__,
        "dry_run_default": not _live_capable(),
        "brands": [
            {
                "slug": b.slug,
                "display_name": b.display_name,
                "docs": len(list(b.knowledge_dir.glob("*.md"))),
            }
            for b in discover_brands()
        ],
        "engines": [
            {"name": e.name, "status": e.status, "description": e.description}
            for e in default_registry().all()
        ],
    }


@app.get("/api/knowledge/{slug}")
def knowledge(slug: str):
    try:
        brand = Brand.load(slug)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Unknown brand '{slug}'")
    docs = KnowledgeEngine().load(brand)
    return {"docs": [{"name": d.name, "title": d.title, "content": d.content} for d in docs]}


@app.get("/api/pipeline/stages")
def stages():
    return {
        "stages": [
            {"key": s.key, "title": s.title, "instructions": s.instructions}
            for s in PIPELINE
        ]
    }


@app.post("/api/runs")
def create_run(req: RunRequest):
    topic = req.topic.strip()
    if not topic:
        raise HTTPException(status_code=422, detail="Topic must not be empty")
    dry_run = req.dry_run if req.dry_run is not None else not _live_capable()
    try:
        job = manager.start(
            req.brand,
            topic,
            stages=req.stages,
            dry_run=dry_run,
            web_research=req.web_research,
            orchestrate=req.orchestrate,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Unknown brand '{req.brand}'")
    except ValueError as exc:  # unknown stage keys
        raise HTTPException(status_code=422, detail=str(exc))
    return {"job_id": job.id, **job.summary()}


@app.get("/api/runs")
def list_runs():
    return {"runs": manager.list_jobs()}


@app.get("/api/runs/{job_id}")
def get_run(job_id: str):
    try:
        return manager.get(job_id).summary()
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown run '{job_id}'")


@app.get("/api/runs/{job_id}/events")
def run_events(job_id: str, start: int = 0):
    try:
        manager.get(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown run '{job_id}'")

    def stream():
        for event in manager.iter_events(job_id, start=start):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
