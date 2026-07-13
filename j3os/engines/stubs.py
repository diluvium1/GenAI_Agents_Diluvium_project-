"""Planned J3OS engines.

These define the contracts for the rest of the operating system so
future modules land in known slots. Each raises ``NotImplementedError``
with a pointer to its roadmap phase; promoting one to active means
giving it its own package under ``j3os/engines/`` like knowledge and
editorial.
"""

from __future__ import annotations

from typing import Any

from j3os.core.brand import Brand
from j3os.core.engine import Engine


class _PlannedEngine(Engine):
    status = "planned"
    phase: str = ""

    def run(self, brand: Brand, **kwargs: Any) -> Any:
        raise NotImplementedError(
            f"The {self.name} engine is planned for {self.phase}. "
            "See docs/J3OS_ORCHESTRATION_PLAN.md."
        )


class BrandEngine(_PlannedEngine):
    name = "brand"
    description = "Identity systems: naming, voice codification, brand launch kits."
    phase = "Phase 2"


class DesignEngine(_PlannedEngine):
    name = "design"
    description = "Design system generation: templates, layouts, image direction at scale."
    phase = "Phase 2"


class CommerceEngine(_PlannedEngine):
    name = "commerce"
    description = "Affiliate link management, product data, ShopMy/LTK/Amazon integrations."
    phase = "Phase 2"


class AutomationEngine(_PlannedEngine):
    name = "automation"
    description = "Scheduling, publishing, and workflow automation across channels."
    phase = "Phase 2"


class AnalyticsEngine(_PlannedEngine):
    name = "analytics"
    description = "Performance measurement: traffic, revenue attribution, content scoring."
    phase = "Phase 3"


class AIStudioEngine(_PlannedEngine):
    name = "ai_studio"
    description = "Interactive generation workspace built on the shared knowledge core."
    phase = "Phase 3"


class ResearchEngine(_PlannedEngine):
    name = "research"
    description = "Standing market/trend research that feeds the Knowledge Engine."
    phase = "Phase 3"


PLANNED_ENGINES: list[Engine] = [
    BrandEngine(),
    DesignEngine(),
    CommerceEngine(),
    AutomationEngine(),
    AnalyticsEngine(),
    AIStudioEngine(),
    ResearchEngine(),
]
