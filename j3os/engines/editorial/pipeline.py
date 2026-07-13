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

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from j3os.core import llm
from j3os.core.brand import Brand
from j3os.engines.knowledge.engine import KnowledgeEngine


@dataclass(frozen=True)
class PipelineStage:
    key: str            # slug used for filenames and --stages selection
    title: str
    instructions: str   # what this stage must produce
    max_tokens: int = 16000


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


def run_pipeline(
    brand: Brand,
    topic: str,
    *,
    stages: list[str] | None = None,
    dry_run: bool | None = None,
    output_root: Path | None = None,
) -> PipelineResult:
    """Run the editorial pipeline for a topic, writing each artifact to
    the brand's output directory as markdown."""
    selected = stages or STAGE_KEYS
    unknown = set(selected) - set(STAGE_KEYS)
    if unknown:
        raise ValueError(f"Unknown stages: {sorted(unknown)}. Valid: {STAGE_KEYS}")

    knowledge = KnowledgeEngine()
    system = knowledge.context_block(brand)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    slug = "-".join(topic.lower().split())[:60]
    out_dir = (output_root or brand.output_dir) / f"{stamp}-{slug}"
    out_dir.mkdir(parents=True, exist_ok=True)

    result = PipelineResult(brand=brand, topic=topic, output_dir=out_dir)
    for index, stage in enumerate(PIPELINE, start=1):
        if stage.key not in selected:
            continue
        prompt = _stage_prompt(stage, topic, result.artifacts)
        content = llm.generate(
            system, prompt, dry_run=dry_run, max_tokens=stage.max_tokens
        )
        result.artifacts[stage.key] = content
        (out_dir / f"{index:02d}_{stage.key}.md").write_text(
            content, encoding="utf-8"
        )
    return result
