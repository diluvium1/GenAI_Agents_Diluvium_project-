"""J3OS core tests — run with: python -m pytest j3os/tests -q

All tests run offline (the pipeline test uses dry-run mode).
"""

from __future__ import annotations

import pytest

from j3os.core.brand import Brand, discover_brands
from j3os.core.engine import default_registry
from j3os.engines.editorial.pipeline import PIPELINE, STAGE_KEYS, run_pipeline
from j3os.engines.knowledge.engine import KnowledgeEngine

GC = "glass-and-counsel"


def test_glass_and_counsel_is_installed():
    slugs = [b.slug for b in discover_brands()]
    assert GC in slugs


def test_brand_display_name_from_project_doc():
    brand = Brand.load(GC)
    assert brand.display_name == "Glass & Counsel™"


def test_knowledge_engine_loads_canonical_docs_in_order():
    docs = KnowledgeEngine().load(Brand.load(GC))
    names = [d.name for d in docs]
    assert names == [
        "00_PROJECT",
        "01_BRAND",
        "02_POSITIONING",
        "03_ICP",
        "04_EDITORIAL",
        "05_CREATIVE",
        "06_MONETIZATION",
        "07_AI",
        "08_ROADMAP",
    ]


def test_knowledge_search_and_get():
    engine = KnowledgeEngine()
    brand = Brand.load(GC)
    assert engine.get(brand, "03_ICP").title == "Ideal Customer Profiles"
    hits = engine.search(brand, "Sage")
    assert any(d.name == "01_BRAND" for d in hits)


def test_context_block_contains_brand_promise_and_all_docs():
    context = KnowledgeEngine().context_block(Brand.load(GC))
    assert "Beauty with Good Judgment" in context
    assert context.count("<document name=") == 9


def test_default_registry_has_all_engines():
    registry = default_registry()
    active = {e.name for e in registry.all() if e.status == "active"}
    planned = {e.name for e in registry.all() if e.status == "planned"}
    assert active == {"knowledge", "editorial"}
    assert planned == {
        "brand",
        "design",
        "commerce",
        "automation",
        "analytics",
        "ai_studio",
        "research",
    }


def test_planned_engine_raises_with_pointer():
    registry = default_registry()
    with pytest.raises(NotImplementedError, match="ORCHESTRATION_PLAN"):
        registry.get("commerce").run(Brand.load(GC))


def test_pipeline_stage_order_matches_spec():
    assert STAGE_KEYS == [
        "research",
        "brief",
        "seo_outline",
        "article",
        "newsletter",
        "instagram_carousel",
        "pinterest_pins",
        "amazon_review",
        "email",
        "hero_images",
        "scheduling_queue",
    ]
    assert len(PIPELINE) == 11


def test_pipeline_dry_run_grounds_every_stage_in_knowledge(tmp_path):
    brand = Brand.load(GC)
    result = run_pipeline(
        brand,
        "The 5 best glass desk accessories",
        stages=["research", "brief"],
        dry_run=True,
        output_root=tmp_path,
    )
    assert set(result.artifacts) == {"research", "brief"}
    # Every stage's system prompt embeds the full knowledge base.
    assert "Beauty with Good Judgment" in result.artifacts["research"]
    # Downstream stages receive upstream artifacts.
    assert '<artifact stage="research">' in result.artifacts["brief"]
    # Artifacts are written to disk with ordered filenames.
    written = sorted(p.name for p in result.output_dir.glob("*.md"))
    assert written == ["01_research.md", "02_brief.md"]


def test_pipeline_rejects_unknown_stage(tmp_path):
    with pytest.raises(ValueError, match="Unknown stages"):
        run_pipeline(
            Brand.load(GC),
            "topic",
            stages=["tiktok"],
            dry_run=True,
            output_root=tmp_path,
        )
