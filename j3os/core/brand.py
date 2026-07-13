"""Brand identity and filesystem layout.

A brand is a directory under ``j3os/brands/<slug>/`` containing a
``knowledge/`` folder of canonical markdown documents (the Brand Bible,
ICP, editorial standards, etc.). Every engine receives a ``Brand`` and
reads its knowledge through the Knowledge Engine before generating
anything — that rule is codified in each brand's ``07_AI.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

BRANDS_ROOT = Path(__file__).resolve().parent.parent / "brands"


@dataclass(frozen=True)
class Brand:
    slug: str
    root: Path

    @property
    def knowledge_dir(self) -> Path:
        return self.root / "knowledge"

    @property
    def output_dir(self) -> Path:
        return self.root / "output"

    @property
    def display_name(self) -> str:
        # First H1 of 00_PROJECT.md is the canonical brand name.
        project = self.knowledge_dir / "00_PROJECT.md"
        if project.exists():
            for line in project.read_text(encoding="utf-8").splitlines():
                if line.startswith("# "):
                    return line[2:].strip()
        return self.slug

    @classmethod
    def load(cls, slug: str, brands_root: Path = BRANDS_ROOT) -> "Brand":
        root = brands_root / slug
        if not (root / "knowledge").is_dir():
            raise FileNotFoundError(
                f"Brand '{slug}' not found (expected knowledge dir at {root / 'knowledge'})"
            )
        return cls(slug=slug, root=root)


def discover_brands(brands_root: Path = BRANDS_ROOT) -> list[Brand]:
    """Return every brand that has a knowledge directory."""
    if not brands_root.is_dir():
        return []
    return [
        Brand(slug=p.name, root=p)
        for p in sorted(brands_root.iterdir())
        if (p / "knowledge").is_dir()
    ]
