"""System 02 — Editorial Production Engine."""

from __future__ import annotations

from typing import Any

from j3os.core.brand import Brand
from j3os.core.engine import Engine
from j3os.engines.editorial.pipeline import PipelineResult, run_pipeline


class EditorialEngine(Engine):
    name = "editorial"
    description = (
        "System 02 — turns one topic into a full multi-channel asset kit "
        "(research → article → newsletter → social → commerce → scheduling)."
    )
    status = "active"

    def run(
        self,
        brand: Brand,
        *,
        topic: str,
        stages: list[str] | None = None,
        dry_run: bool | None = None,
        **kwargs: Any,
    ) -> PipelineResult:
        return run_pipeline(brand, topic, stages=stages, dry_run=dry_run)
