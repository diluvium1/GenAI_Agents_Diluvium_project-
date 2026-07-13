"""Offline tests for Loop 2: grading (review), batch calendar, web research,
and the CLI surface. Everything runs in dry-run mode — no API key required."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from j3os.core.brand import Brand
from j3os.engines.editorial.pipeline import run_pipeline

GC = "glass-and-counsel"
CALENDAR_EXAMPLE = (
    Path(__file__).resolve().parent.parent
    / "brands"
    / GC
    / "calendar.example.json"
)


def test_review_run_dry(tmp_path):
    from j3os.engines.editorial.review import review_run

    brand = Brand.load(GC)
    run = run_pipeline(
        brand, "review me", stages=["research"], dry_run=True, output_root=tmp_path
    )
    result = review_run(brand, run.output_dir, dry_run=True)

    # Dry-run stage responses are unparseable by design → no score.
    assert result.reviews["research"].score is None

    review_dir = run.output_dir / "review"
    scores_path = review_dir / "scores.json"
    scorecard_path = review_dir / "scorecard.md"
    assert scores_path.exists()
    assert scorecard_path.exists()

    scores = json.loads(scores_path.read_text())
    assert isinstance(scores, dict)


def test_run_calendar_dry(tmp_path):
    from j3os.engines.editorial.batch import run_calendar

    brand = Brand.load(GC)
    result = run_calendar(
        brand,
        ["t one", "t two"],
        stages=["research"],
        dry_run=True,
        output_root=tmp_path,
    )

    assert set(result.artifacts) == {"t one", "t two"}
    for topic in ("t one", "t two"):
        assert "research" in result.artifacts[topic]

    manifest = json.loads((result.output_dir / "calendar_manifest.json").read_text())
    assert len(manifest["topics"]) == 2

    # Per-topic artifact files exist somewhere under the output dir.
    assert list(result.output_dir.rglob("*research*.md"))


def test_load_calendar_and_validation(tmp_path):
    from j3os.engines.editorial.batch import load_calendar

    topics = load_calendar(CALENDAR_EXAMPLE)
    assert len(topics) >= 3

    bad = tmp_path / "empty.json"
    bad.write_text("{}")
    with pytest.raises(ValueError):
        load_calendar(bad)


def test_web_research_dry(tmp_path):
    brand = Brand.load(GC)
    result = run_pipeline(
        brand,
        "web me",
        stages=["research"],
        dry_run=True,
        output_root=tmp_path,
        web_research=True,
    )
    assert "[web-search: enabled]" in result.artifacts["research"]

    manifest = json.loads((result.output_dir / "manifest.json").read_text())
    assert manifest["web_research"] is True


def test_cli_help_lists_commands():
    proc = subprocess.run(
        [sys.executable, "-m", "j3os", "--help"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    for command in ("grade", "batch", "serve"):
        assert command in proc.stdout
