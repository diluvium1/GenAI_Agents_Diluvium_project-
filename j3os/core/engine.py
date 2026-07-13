"""Engine contract and registry.

J3OS is a set of engines that plug into a shared core:

    Brand Engine · Editorial Engine · Commerce Engine
    Design Engine · Knowledge Engine · Automation Engine
    Analytics · AI Studio · Research

Each engine implements the same minimal contract so future companies
(Launchly, Praxis, Paranormal Gaia, J3P0_DEV, ...) can plug into the
same operating system while keeping their own identity and voice.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from j3os.core.brand import Brand


class Engine(ABC):
    """Base contract for every J3OS engine."""

    #: machine name, e.g. "editorial"
    name: str = ""
    #: one-line human description
    description: str = ""
    #: implementation status: "active" | "planned"
    status: str = "planned"

    @abstractmethod
    def run(self, brand: Brand, **kwargs: Any) -> Any:
        """Execute the engine's primary workflow for a brand."""


class EngineRegistry:
    """Registry mapping engine names to instances."""

    def __init__(self) -> None:
        self._engines: dict[str, Engine] = {}

    def register(self, engine: Engine) -> Engine:
        if not engine.name:
            raise ValueError(f"{type(engine).__name__} has no name")
        if engine.name in self._engines:
            raise ValueError(f"Engine '{engine.name}' already registered")
        self._engines[engine.name] = engine
        return engine

    def get(self, name: str) -> Engine:
        try:
            return self._engines[name]
        except KeyError:
            raise KeyError(
                f"Unknown engine '{name}'. Available: {', '.join(sorted(self._engines))}"
            ) from None

    def all(self) -> list[Engine]:
        return list(self._engines.values())

    def __contains__(self, name: str) -> bool:
        return name in self._engines


def default_registry() -> EngineRegistry:
    """Build the standard J3OS registry with all engines installed."""
    from j3os.engines.editorial.engine import EditorialEngine
    from j3os.engines.knowledge.engine import KnowledgeEngine
    from j3os.engines.stubs import PLANNED_ENGINES

    registry = EngineRegistry()
    registry.register(KnowledgeEngine())
    registry.register(EditorialEngine())
    for engine in PLANNED_ENGINES:
        registry.register(engine)
    return registry
