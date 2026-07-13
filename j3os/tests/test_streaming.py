"""Offline tests for the pipeline progress/streaming contract."""

from __future__ import annotations

import json

from j3os.core.brand import Brand
from j3os.engines.editorial.pipeline import run_pipeline

GC = "glass-and-counsel"


def test_progress_event_ordering(tmp_path):
    events: list[dict] = []
    run_pipeline(
        Brand.load(GC),
        "test topic",
        stages=["research", "brief"],
        dry_run=True,
        output_root=tmp_path,
        progress=events.append,
    )
    kinds = [e["event"] for e in events]
    assert kinds == [
        "run_started",
        "stage_started",
        "text",
        "stage_completed",
        "stage_started",
        "text",
        "stage_completed",
        "run_completed",
    ]
    assert events[0]["stages"] == ["research", "brief"]
    assert events[1]["stage"] == "research" and events[1]["index"] == 1
    assert events[4]["stage"] == "brief" and events[4]["index"] == 2
    # dry-run emits the full rendered prompt as a single text delta
    assert "Beauty with Good Judgment" in events[2]["delta"]
    assert events[3]["chars"] == len(events[2]["delta"])


def test_manifest_written_per_stage(tmp_path):
    result = run_pipeline(
        Brand.load(GC),
        "manifest check",
        stages=["research"],
        dry_run=True,
        output_root=tmp_path,
    )
    manifest = json.loads((result.output_dir / "manifest.json").read_text())
    assert manifest["brand"] == GC
    assert manifest["topic"] == "manifest check"
    assert manifest["dry_run"] is True
    assert [s["key"] for s in manifest["stages"]] == ["research"]
    assert manifest["stages"][0]["file"] == "01_research.md"
    assert manifest["stages"][0]["chars"] > 0


def test_orchestrate_routes_adapt_stages(tmp_path, monkeypatch):
    from j3os.core import llm
    from j3os.engines.editorial import pipeline as pl

    seen: dict[str, str | None] = {}
    real = llm.generate

    def spy(system, prompt, *, model=None, **kw):
        # first line after "Task —" identifies the stage title
        seen[len(seen)] = model
        return real(system, prompt, model=model, **kw)

    monkeypatch.setattr(pl.llm, "generate", spy)
    result = pl.run_pipeline(
        Brand.load(GC),
        "routing check",
        stages=["research", "seo_outline"],
        dry_run=True,
        output_root=tmp_path,
        orchestrate=True,
    )
    # research is judgment tier (default model = None), seo_outline is adapt
    assert seen[0] is None
    assert seen[1] == llm.ADAPT_MODEL
    manifest = json.loads((result.output_dir / "manifest.json").read_text())
    assert manifest["orchestrate"] is True


def test_progress_none_is_unchanged(tmp_path):
    result = run_pipeline(
        Brand.load(GC),
        "no progress",
        stages=["research"],
        dry_run=True,
        output_root=tmp_path,
    )
    assert set(result.artifacts) == {"research"}
