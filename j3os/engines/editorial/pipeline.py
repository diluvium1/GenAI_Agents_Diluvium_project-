"""System 02 — Editorial Production Engine pipeline.

The factory. One topic goes in; a full multi-channel asset kit comes out:

    Research → Editorial Brief → SEO Outline → Long-form Article
    → Newsletter → Instagram Carousel → Pinterest Pins → Amazon Review
    → Email → Hero Images → Scheduling Queue

Every stage references the Knowledge Engine before generation: the brand
context is the system prompt for every call, and each stage receives the
outputs of the stages before it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from j3os.core import llm
from j3os.core.brand import Brand
from j3os.engines.knowledge.engine import KnowledgeEngine


@dataclass(frozen=True)
class PipelineStage:
    key: str            # slug used for filenames and --stages selection
    title: str
    instructions: str   # what this stage must produce
    max_tokens: int = 16000
    web_search: bool = False  # ground this stage with live web search when enabled
    tier: str = "adapt"  # "judgment" needs frontier reasoning; "adapt" reshapes
                         # upstream artifacts and routes cheaper under orchestration


PIPELINE: list[PipelineStage] = [
    PipelineStage(
        key="research",
        title="Research",
        instructions=(
            "Produce a research memo on the topic for the editorial team: what "
            "the ICP already believes, what questions she is actually asking, "
            "what the competitive coverage looks like, which products or "
            "approaches are credible (with evidence), and which angles fit the "
            "brand's editorial pillars. Cite reasoning, flag uncertainty, and "
            "end with the 3 strongest angles ranked."
        ),
        web_search=True,
        tier="judgment",
    ),
    PipelineStage(
        key="brief",
        title="Editorial Brief",
        instructions=(
            "Turn the research into an editorial brief: chosen angle, working "
            "headline options (5), the reader promise, the judgment we are "
            "offering (what we recommend and what we deliberately leave out), "
            "target feature format from the weekly features list, products to "
            "feature with selection rationale, and what 'done well' looks like."
        ),
        tier="judgment",
    ),
    PipelineStage(
        key="seo_outline",
        title="SEO Outline",
        instructions=(
            "Produce an SEO outline for the article: primary keyword, secondary "
            "keywords, search intent analysis, title tag and meta description, "
            "URL slug, H2/H3 structure with what each section must cover, "
            "internal-link opportunities, and FAQ schema questions. Stay "
            "editorial — no keyword stuffing, no clickbait."
        ),
    ),
    PipelineStage(
        key="article",
        title="Long-form Article",
        instructions=(
            "Write the full long-form article following the brief and the SEO "
            "outline. Editorial voice per the Brand Bible: warm, witty, "
            "competent, calm. Recommend less, explain more. Include natural "
            "placements for affiliate products with honest, evidence-led "
            "reasoning, and a 'the counsel' verdict section. 1,500–2,500 words."
        ),
        max_tokens=32000,
        tier="judgment",
    ),
    PipelineStage(
        key="newsletter",
        title="Newsletter",
        instructions=(
            "Adapt the article into a newsletter edition: subject line options "
            "(5, tested against the ICP), preview text, a warm editor's-note "
            "opening, the condensed insight, one clear product recommendation "
            "block, and a soft CTA to the full article. Keep it scannable."
        ),
    ),
    PipelineStage(
        key="instagram_carousel",
        title="Instagram Carousel",
        instructions=(
            "Create an Instagram carousel from the article: 8–10 slides, each "
            "with on-slide copy (max ~20 words), an art-direction note per "
            "slide consistent with the creative direction (quiet luxury, "
            "editorial, generous whitespace), plus the caption with hook, "
            "value, CTA, and hashtag set."
        ),
    ),
    PipelineStage(
        key="pinterest_pins",
        title="Pinterest Pins",
        instructions=(
            "Create 5 Pinterest pin concepts: pin title, pin description with "
            "keywords, text overlay copy, art direction per the design system, "
            "and the board(s) each pin belongs to. Pinterest is a primary "
            "discovery channel for the ICP — optimize for saves."
        ),
    ),
    PipelineStage(
        key="amazon_review",
        title="Amazon Review",
        instructions=(
            "Write the standalone product review for the featured product "
            "(Amazon Associates): honest evaluation per the review philosophy "
            "— recommend less, explain more, never overpromise. Include who "
            "it's for, who should skip it, evidence and comparisons, and the "
            "'Worth It?' verdict."
        ),
        tier="judgment",
    ),
    PipelineStage(
        key="email",
        title="Email",
        instructions=(
            "Write a short standalone promotional email (distinct from the "
            "newsletter): one idea, one product, one CTA. Subject line options "
            "(3), body under 200 words, elegant and direct, zero spam energy."
        ),
    ),
    PipelineStage(
        key="hero_images",
        title="Hero Images",
        instructions=(
            "Write hero-image production notes: 3 concepts for the article "
            "hero, each with a detailed art-direction description (composition, "
            "surfaces, light, styling, palette) following the creative "
            "direction, plus a text-to-image prompt version of each, and crop "
            "specs for web, newsletter, Instagram, and Pinterest."
        ),
        tier="judgment",
    ),
    PipelineStage(
        key="scheduling_queue",
        title="Scheduling Queue",
        instructions=(
            "Produce the scheduling queue for this asset kit: a 14-day "
            "publish plan mapping every asset to channel, date offset (day 0 = "
            "article publish), time-of-day rationale for the ICP, and "
            "cross-promotion notes. Output as a markdown table plus notes."
        ),
    ),
]

STAGE_KEYS = [s.key for s in PIPELINE]


@dataclass
class PipelineResult:
    brand: Brand
    topic: str
    output_dir: Path
    artifacts: dict[str, str] = field(default_factory=dict)


def _stage_prompt(stage: PipelineStage, topic: str, artifacts: dict[str, str]) -> str:
    parts = [f"Topic: {topic}", "", f"Task — {stage.title}:", stage.instructions]
    if artifacts:
        parts.append("")
        parts.append(
            "Upstream pipeline artifacts (build on these; stay consistent with them):"
        )
        for key, content in artifacts.items():
            parts.append(f"\n<artifact stage=\"{key}\">\n{content.strip()}\n</artifact>")
    return "\n".join(parts)


ProgressCallback = Optional[Callable[[dict], None]]


def run_pipeline(
    brand: Brand,
    topic: str,
    *,
    stages: list[str] | None = None,
    dry_run: bool | None = None,
    output_root: Path | None = None,
    progress: ProgressCallback = None,
    web_research: bool = False,
    orchestrate: bool = False,
) -> PipelineResult:
    """Run the editorial pipeline for a topic, writing each artifact to
    the brand's output directory as markdown.

    ``progress``, when provided, receives event dicts as the run advances:
    ``run_started``, then per stage ``stage_started`` / ``text`` (streamed
    deltas) / ``stage_completed``, and finally ``run_completed``. A
    ``manifest.json`` is written to the output dir and updated after every
    stage, so a crashed run still leaves a partial manifest.

    ``web_research``, when True, enables live web-search grounding for the
    stages that opt into it (those with ``stage.web_search``). When False
    (the default) no stage uses web search.
    """
    selected = stages or STAGE_KEYS
    unknown = set(selected) - set(STAGE_KEYS)
    if unknown:
        raise ValueError(f"Unknown stages: {sorted(unknown)}. Valid: {STAGE_KEYS}")
    selected = [k for k in STAGE_KEYS if k in set(selected)]

    knowledge = KnowledgeEngine()
    system = knowledge.context_block(brand)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    slug = "-".join(topic.lower().split())[:60]
    out_dir = (output_root or brand.output_dir) / f"{stamp}-{slug}"
    out_dir.mkdir(parents=True, exist_ok=True)

    def emit(event: dict) -> None:
        if progress is not None:
            progress(event)

    resolved_dry_run = dry_run if dry_run is not None else llm.is_dry_run()
    manifest: dict = {
        "brand": brand.slug,
        "topic": topic,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": resolved_dry_run,
        "web_research": bool(web_research),
        "orchestrate": bool(orchestrate),
        "stages": [],
    }

    def write_manifest() -> None:
        (out_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

    write_manifest()
    emit(
        {
            "event": "run_started",
            "brand": brand.slug,
            "topic": topic,
            "stages": selected,
            "output_dir": str(out_dir),
        }
    )

    result = PipelineResult(brand=brand, topic=topic, output_dir=out_dir)
    for index, stage in enumerate(PIPELINE, start=1):
        if stage.key not in selected:
            continue
        emit(
            {
                "event": "stage_started",
                "stage": stage.key,
                "index": index,
                "title": stage.title,
            }
        )
        on_text = None
        if progress is not None:
            on_text = lambda delta, key=stage.key: emit(
                {"event": "text", "stage": key, "delta": delta}
            )
        stage_model = (
            llm.ADAPT_MODEL if orchestrate and stage.tier == "adapt" else None
        )
        prompt = _stage_prompt(stage, topic, result.artifacts)
        content = llm.generate(
            system,
            prompt,
            dry_run=dry_run,
            max_tokens=stage.max_tokens,
            on_text=on_text,
            model=stage_model,
            web_search=web_research and stage.web_search,
        )
        result.artifacts[stage.key] = content
        filename = f"{index:02d}_{stage.key}.md"
        path = out_dir / filename
        path.write_text(content, encoding="utf-8")
        manifest["stages"].append(
            {
                "key": stage.key,
                "title": stage.title,
                "file": filename,
                "chars": len(content),
            }
        )
        write_manifest()
        emit(
            {
                "event": "stage_completed",
                "stage": stage.key,
                "index": index,
                "chars": len(content),
                "path": str(path),
            }
        )

    emit(
        {
            "event": "run_completed",
            "artifacts": list(result.artifacts),
            "output_dir": str(out_dir),
        }
    )
    return result
