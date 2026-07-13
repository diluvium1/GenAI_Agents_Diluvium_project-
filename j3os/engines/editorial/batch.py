"""System 02 — Editorial batch mode (run a whole content calendar).

The pipeline (``pipeline.py``) turns one topic into a full asset kit,
one stage at a time. Batch mode runs a *calendar* of N topics through
that same pipeline using the Anthropic Message Batches API, which bills
at 50% of standard rates.

Because the pipeline stages chain (the brief needs the research, the
article needs the brief, …), batching happens **stage-parallel across
topics**: for each selected stage, in pipeline order, we submit one
batch containing that stage's request for every topic — each request's
prompt embeds that topic's own upstream artifacts — wait for the batch
to finish, collect the results keyed by ``custom_id``, then advance to
the next stage. A crashed run leaves a partial ``calendar_manifest.json``
because it is rewritten after every stage.

Dry-run mode (``J3OS_DRY_RUN=1`` or ``dry_run=True``) never touches the
API: it calls :func:`j3os.core.llm.generate` sequentially per topic so
the whole thing stays offline for tests and prompt previews.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from j3os.core import llm
from j3os.core.brand import Brand
from j3os.engines.editorial.pipeline import PIPELINE, STAGE_KEYS, _stage_prompt
from j3os.engines.knowledge.engine import KnowledgeEngine


def _slug(topic: str) -> str:
    """Filesystem-safe topic slug, matching the pipeline's convention."""
    return "-".join(topic.lower().split())[:60]


def load_calendar(path: Path) -> list[str]:
    """Load a content calendar from JSON.

    Accepts either a bare list of topic strings or an object with a
    ``"topics"`` key holding that list. Raises ``ValueError`` with a
    clear message if the shape is wrong or any topic is empty.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        topics = data.get("topics")
    else:
        topics = data
    if not isinstance(topics, list) or not topics:
        raise ValueError(
            f"Calendar {path} must be a non-empty list of topics "
            "(or an object with a non-empty 'topics' list)."
        )
    cleaned: list[str] = []
    for item in topics:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"Calendar {path} contains a non-string or empty topic: {item!r}"
            )
        cleaned.append(item.strip())
    return cleaned


@dataclass
class CalendarResult:
    brand: Brand
    topics: list[str]
    output_dir: Path
    # artifacts[topic][stage] -> generated markdown
    artifacts: dict[str, dict[str, str]] = field(default_factory=dict)


def run_calendar(
    brand: Brand,
    topics: list[str],
    *,
    stages: list[str] | None = None,
    dry_run: bool | None = None,
    output_root: Path | None = None,
    poll_interval: float = 30.0,
) -> CalendarResult:
    """Run a content calendar through the editorial pipeline in batch mode.

    For each selected stage, in pipeline order, one Message Batch carries
    that stage's request for every topic; the batch is polled until it
    ends, results are collected by ``custom_id``, and each artifact is
    written before the next stage begins. Returns a :class:`CalendarResult`
    whose ``artifacts`` maps every topic to its per-stage outputs.
    """
    selected = stages or STAGE_KEYS
    unknown = set(selected) - set(STAGE_KEYS)
    if unknown:
        raise ValueError(f"Unknown stages: {sorted(unknown)}. Valid: {STAGE_KEYS}")
    selected_stages = [s for s in PIPELINE if s.key in set(selected)]

    knowledge = KnowledgeEngine()
    system = knowledge.context_block(brand)

    resolved_dry_run = dry_run if dry_run is not None else llm.is_dry_run()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = (output_root or brand.output_dir) / f"{stamp}-calendar"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Stable slug per topic, and per-topic output directory.
    slugs = {topic: _slug(topic) for topic in topics}
    topic_by_slug = {slug: topic for topic, slug in slugs.items()}
    for slug in slugs.values():
        (out_dir / slug).mkdir(parents=True, exist_ok=True)

    result = CalendarResult(
        brand=brand,
        topics=list(topics),
        output_dir=out_dir,
        artifacts={topic: {} for topic in topics},
    )

    # Stage index in the full pipeline drives the NN_ filename prefix.
    stage_index = {stage.key: i for i, stage in enumerate(PIPELINE, start=1)}

    manifest: dict = {
        "brand": brand.slug,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": resolved_dry_run,
        "topics": [{"topic": topic, "slug": slugs[topic]} for topic in topics],
        "stages": [s.key for s in selected_stages],
        "files": {slug: {} for slug in slugs.values()},
    }

    def write_manifest() -> None:
        (out_dir / "calendar_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

    def store(topic: str, stage_key: str, content: str) -> None:
        result.artifacts[topic][stage_key] = content
        slug = slugs[topic]
        filename = f"{stage_index[stage_key]:02d}_{stage_key}.md"
        (out_dir / slug / filename).write_text(content, encoding="utf-8")
        manifest["files"][slug][stage_key] = filename

    write_manifest()

    if resolved_dry_run:
        for stage in selected_stages:
            for topic in topics:
                prompt = _stage_prompt(stage, topic, result.artifacts[topic])
                content = llm.generate(system, prompt, dry_run=True)
                store(topic, stage.key, content)
            write_manifest()
        return result

    # Live path: one Message Batch per stage.
    import anthropic
    from anthropic.types.message_create_params import (
        MessageCreateParamsNonStreaming,
    )
    from anthropic.types.messages.batch_create_params import Request

    client = anthropic.Anthropic()

    for stage in selected_stages:
        requests = []
        for topic in topics:
            prompt = _stage_prompt(stage, topic, result.artifacts[topic])
            requests.append(
                Request(
                    custom_id=f"{slugs[topic]}::{stage.key}",
                    params=MessageCreateParamsNonStreaming(
                        model=llm.MODEL,
                        max_tokens=stage.max_tokens,
                        system=[
                            {
                                "type": "text",
                                "text": system,
                                "cache_control": {"type": "ephemeral", "ttl": "1h"},
                            }
                        ],
                        messages=[{"role": "user", "content": prompt}],
                    ),
                )
            )

        batch = client.messages.batches.create(requests=requests)
        while True:
            batch = client.messages.batches.retrieve(batch.id)
            if batch.processing_status == "ended":
                break
            time.sleep(poll_interval)

        for entry in client.messages.batches.results(batch.id):
            slug, _, stage_key = entry.custom_id.partition("::")
            topic = topic_by_slug.get(slug)
            if topic is None or stage_key != stage.key:
                continue
            outcome = entry.result
            if outcome.type == "succeeded":
                content = "".join(
                    block.text
                    for block in outcome.message.content
                    if block.type == "text"
                )
            else:
                content = f"[batch error: {outcome.type}]"
            store(topic, stage.key, content)

        write_manifest()

    return result
