"""System 01 — Brand Knowledge Engine.

The brain. It stores and serves the permanent source of truth for a
brand: Brand Bibles, ICPs, editorial guidelines, style guides, creative
direction, commerce rules, AI instructions, research, SOPs, and
roadmaps. Every AI workflow starts here — no engine generates anything
without first assembling its context from this engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from j3os.core.brand import Brand
from j3os.core.engine import Engine


@dataclass(frozen=True)
class KnowledgeDoc:
    name: str          # e.g. "01_BRAND"
    path: Path
    content: str

    @property
    def title(self) -> str:
        for line in self.content.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return self.name


class KnowledgeEngine(Engine):
    name = "knowledge"
    description = "System 01 — stores and serves each brand's canonical knowledge."
    status = "active"

    def load(self, brand: Brand) -> list[KnowledgeDoc]:
        """Load every knowledge document for a brand, in canonical order."""
        docs = []
        for path in sorted(brand.knowledge_dir.glob("*.md")):
            docs.append(
                KnowledgeDoc(
                    name=path.stem,
                    path=path,
                    content=path.read_text(encoding="utf-8"),
                )
            )
        if not docs:
            raise FileNotFoundError(f"No knowledge documents in {brand.knowledge_dir}")
        return docs

    def get(self, brand: Brand, name: str) -> KnowledgeDoc:
        """Fetch a single document by stem (e.g. '03_ICP')."""
        for doc in self.load(brand):
            if doc.name == name:
                return doc
        raise KeyError(f"No knowledge doc '{name}' for brand '{brand.slug}'")

    def search(self, brand: Brand, term: str) -> list[KnowledgeDoc]:
        """Case-insensitive full-text search across a brand's knowledge."""
        needle = term.lower()
        return [d for d in self.load(brand) if needle in d.content.lower()]

    def context_block(self, brand: Brand) -> str:
        """Assemble the full brand context used as the system prompt for
        every generation. This is the codified form of 07_AI.md: read the
        Brand Bible, ICP, editorial standards, design system, and commerce
        rules before creating anything."""
        docs = self.load(brand)
        sections = "\n\n".join(
            f"<document name=\"{d.name}\">\n{d.content.strip()}\n</document>"
            for d in docs
        )
        return (
            f"You are the in-house AI staff of {brand.display_name}, a company "
            "that runs on J3OS. The documents below are the permanent source "
            "of truth for this brand. Every output must be consistent with "
            "them — voice, audience, editorial standards, creative direction, "
            "and commerce rules. Outputs must feel editorial, helpful, "
            "beautiful, and trustworthy. Never clickbait. Never spam.\n\n"
            f"{sections}"
        )

    def run(self, brand: Brand, **kwargs: Any) -> str:
        """Default workflow: return the assembled context block."""
        return self.context_block(brand)
