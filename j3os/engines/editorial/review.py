"""System 02 — Editorial Review Engine (the editor-in-chief).

Where the pipeline is the factory, this is the quality desk. It grades a
completed pipeline run's artifacts against the brand's editorial
standards (``04_EDITORIAL.md`` and the rest of the knowledge base) and
writes a readable scorecard.

Each stage artifact is judged strictly on the same axes the brand lives
by: voice (warm, witty, competent, calm), the review philosophy
(recommend less, explain more, never overpromise), fit with the ICP, and
the absence of clickbait or spam. Every review is grounded in the full
Knowledge Engine context block, exactly as generation is.

Runs in dry-run mode return the rendered prompt instead of a graded
review; the lenient JSON parser is designed to fall back to an
``score=None`` review in that case so the whole flow works offline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from j3os.core import llm
from j3os.core.brand import Brand
from j3os.engines.knowledge.engine import KnowledgeEngine

REVIEWER_CHARTER = (
    "\n\n---\n\n"
    "You are the editor-in-chief of this brand. Your job is to grade work "
    "strictly against the Editorial Standards (04_EDITORIAL) and the Brand "
    "Bible above — not to be kind. Reward writing that is warm, witty, "
    "competent, and calm; that recommends less and explains more; that "
    "never overpromises; and that fits the ICP precisely. Penalize "
    "clickbait, spam energy, hype, vague filler, off-voice copy, and "
    "anything that would erode the reader's trust. Be specific, honest, and "
    "hard to impress."
)


@dataclass
class StageReview:
    """One editor-in-chief verdict on a single pipeline artifact."""

    stage: str
    score: int | None  # 1–10, or None when the review could not be parsed
    verdict: str
    strengths: list[str] = field(default_factory=list)
    fixes: list[str] = field(default_factory=list)
    raw: str = ""


@dataclass
class ReviewResult:
    """The full graded review of a pipeline run."""

    run_dir: Path
    reviews: dict[str, StageReview]
    scorecard_path: Path


def _review_prompt(topic: str, stage_title: str, content: str) -> str:
    """Build the grading prompt for one stage artifact."""
    return (
        f"Topic: {topic}\n\n"
        f"Grade the following pipeline artifact — the \"{stage_title}\" stage.\n\n"
        "Judge it strictly on: voice (warm, witty, competent, calm); the "
        "review philosophy (recommend less, explain more, never overpromise); "
        "fit with the ICP; and the total absence of clickbait or spam.\n\n"
        "Respond with STRICT JSON only — no prose, no markdown fences, no "
        "commentary before or after. The JSON object must have exactly these "
        "keys:\n"
        '{\n'
        '  "score": <integer 1-10>,\n'
        '  "verdict": "<one sentence>",\n'
        '  "strengths": ["<2-4 short strings>"],\n'
        '  "fixes": ["<2-4 concrete revisions>"]\n'
        '}\n\n'
        f"<artifact stage=\"{stage_title}\">\n{content.strip()}\n</artifact>"
    )


def _parse_review(stage: str, response: str) -> StageReview:
    """Leniently parse a model response into a :class:`StageReview`.

    Extracts the first ``{`` … matching last ``}`` substring and
    ``json.loads`` it. Any failure (including dry-run, where the response is
    the rendered prompt) yields a ``score=None`` review carrying the raw text.
    """
    start = response.find("{")
    end = response.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            data = json.loads(response[start : end + 1])
            score = data.get("score")
            score = int(score) if isinstance(score, (int, float)) else None
            return StageReview(
                stage=stage,
                score=score,
                verdict=str(data.get("verdict", "")).strip(),
                strengths=[str(s) for s in data.get("strengths", []) or []],
                fixes=[str(f) for f in data.get("fixes", []) or []],
                raw=response,
            )
        except (ValueError, TypeError):
            pass
    return StageReview(
        stage=stage,
        score=None,
        verdict="unparseable review",
        strengths=[],
        fixes=[],
        raw=response,
    )


def _average_score(reviews: dict[str, StageReview]) -> float | None:
    scores = [r.score for r in reviews.values() if r.score is not None]
    if not scores:
        return None
    return sum(scores) / len(scores)


def _render_scorecard(
    topic: str,
    reviews: dict[str, StageReview],
    *,
    dry_run: bool,
) -> str:
    """Render the human-readable markdown scorecard."""
    avg = _average_score(reviews)
    avg_label = "n/a" if avg is None else f"{avg:.1f}/10"
    lines = [
        f"# Editorial Scorecard — {topic}",
        "",
        f"**Average score:** {avg_label} "
        f"({len([r for r in reviews.values() if r.score is not None])} of "
        f"{len(reviews)} stages scored)",
    ]
    if dry_run or all(r.score is None for r in reviews.values()):
        lines += [
            "",
            "> _Dry-run review — no scores were produced (the responses are "
            "rendered prompts, not graded reviews)._",
        ]
    for review in reviews.values():
        score_label = "n/a" if review.score is None else f"{review.score}/10"
        lines += [
            "",
            f"## {review.stage} — {score_label}",
            "",
            f"**Verdict:** {review.verdict or '—'}",
        ]
        lines.append("")
        lines.append("**Strengths:**")
        if review.strengths:
            lines += [f"- {s}" for s in review.strengths]
        else:
            lines.append("- —")
        lines.append("")
        lines.append("**Fixes:**")
        if review.fixes:
            lines += [f"- {f}" for f in review.fixes]
        else:
            lines.append("- —")
    return "\n".join(lines) + "\n"


def review_run(
    brand: Brand,
    run_dir: Path,
    *,
    dry_run: bool | None = None,
) -> ReviewResult:
    """Grade every artifact of a completed pipeline run.

    Reads ``manifest.json`` from ``run_dir`` (as written by
    :func:`j3os.engines.editorial.pipeline.run_pipeline`), grades each stage
    artifact against the brand's editorial standards, and writes
    ``review/scores.json`` and ``review/scorecard.md`` into the run dir.
    """
    run_dir = Path(run_dir)
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"No pipeline manifest at {manifest_path} — is {run_dir} a run dir?"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    topic = manifest.get("topic", "")

    system = KnowledgeEngine().context_block(brand) + REVIEWER_CHARTER

    reviews: dict[str, StageReview] = {}
    for stage in manifest.get("stages", []):
        key = stage["key"]
        content = (run_dir / stage["file"]).read_text(encoding="utf-8")
        prompt = _review_prompt(topic, stage.get("title", key), content)
        response = llm.generate(system, prompt, dry_run=dry_run, max_tokens=4000)
        reviews[key] = _parse_review(key, response)

    review_dir = run_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True)

    scores = {
        key: {
            "score": r.score,
            "verdict": r.verdict,
            "strengths": r.strengths,
            "fixes": r.fixes,
        }
        for key, r in reviews.items()
    }
    (review_dir / "scores.json").write_text(
        json.dumps(scores, indent=2), encoding="utf-8"
    )

    resolved_dry_run = dry_run if dry_run is not None else llm.is_dry_run()
    scorecard_path = review_dir / "scorecard.md"
    scorecard_path.write_text(
        _render_scorecard(topic, reviews, dry_run=resolved_dry_run),
        encoding="utf-8",
    )

    return ReviewResult(
        run_dir=run_dir, reviews=reviews, scorecard_path=scorecard_path
    )


def review_latest(brand: Brand, *, dry_run: bool | None = None) -> ReviewResult:
    """Review the newest run under ``brand.output_dir``.

    Run directories are timestamp-prefixed, so the newest is the last by
    name. Raises ``FileNotFoundError`` if the brand has no runs yet.
    """
    output_dir = brand.output_dir
    runs = (
        sorted(p for p in output_dir.iterdir() if p.is_dir())
        if output_dir.is_dir()
        else []
    )
    if not runs:
        raise FileNotFoundError(
            f"No pipeline runs under {output_dir} for brand '{brand.slug}'"
        )
    return review_run(brand, runs[-1], dry_run=dry_run)
