"""Offline tests for the J3OS live console server (dry-run only)."""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from j3os.server.app import app

GC = "glass-and-counsel"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with TestClient(app) as c:
        yield c


def test_status_shape(client):
    data = client.get("/api/status").json()
    assert data["dry_run_default"] is True
    assert GC in [b["slug"] for b in data["brands"]]
    assert {"knowledge", "editorial"} <= {
        e["name"] for e in data["engines"] if e["status"] == "active"
    }


def test_pipeline_stages_endpoint(client):
    stages = client.get("/api/pipeline/stages").json()["stages"]
    assert len(stages) == 11
    assert stages[0]["key"] == "research"
    assert stages[-1]["key"] == "scheduling_queue"


def test_knowledge_endpoint(client):
    docs = client.get(f"/api/knowledge/{GC}").json()["docs"]
    assert len(docs) == 9
    assert docs[0]["name"] == "00_PROJECT"
    assert client.get("/api/knowledge/nope").status_code == 404


def test_run_lifecycle_and_sse(client, tmp_path, monkeypatch):
    # route artifacts away from the repo tree
    import j3os.core.brand as brand_mod

    monkeypatch.setattr(
        brand_mod.Brand, "output_dir", property(lambda self: tmp_path / "out")
    )

    resp = client.post(
        "/api/runs",
        json={"brand": GC, "topic": "test run", "stages": ["research"], "dry_run": True},
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    deadline = time.time() + 10
    while time.time() < deadline:
        snap = client.get(f"/api/runs/{job_id}").json()
        if snap["status"] != "running":
            break
        time.sleep(0.1)
    assert snap["status"] == "completed"

    # SSE replay from the start ends with job_done
    events = []
    with client.stream("GET", f"/api/runs/{job_id}/events?start=0") as stream:
        for line in stream.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
                if events[-1]["event"] == "job_done":
                    break
    kinds = [e["event"] for e in events]
    assert kinds[0] == "run_started"
    assert kinds[-1] == "job_done" and events[-1]["status"] == "completed"
    assert "stage_completed" in kinds

    runs = client.get("/api/runs").json()["runs"]
    assert job_id in [r["id"] for r in runs]


def test_validation_errors(client):
    assert client.post(
        "/api/runs", json={"brand": "nope", "topic": "x", "dry_run": True}
    ).status_code == 404
    assert client.post(
        "/api/runs", json={"brand": GC, "topic": "  ", "dry_run": True}
    ).status_code == 422
    assert client.post(
        "/api/runs",
        json={"brand": GC, "topic": "x", "stages": ["tiktok"], "dry_run": True},
    ).status_code == 422
    assert client.get("/api/runs/doesnotexist").status_code == 404


def test_index_serves_console(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "J3OS" in resp.text
