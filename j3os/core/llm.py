"""Shared Claude client for all J3OS engines.

All generation goes through :func:`generate`, which:

- uses Claude Opus 4.8 with adaptive thinking,
- streams (long editorial outputs would otherwise risk HTTP timeouts),
- caches the brand-knowledge system prompt with a 1-hour TTL so a full
  pipeline run pays for the knowledge context roughly once, not once
  per stage.

Set ``J3OS_DRY_RUN=1`` (or pass ``dry_run=True``) to skip the API and
return the rendered prompt instead — used by tests and for previewing
pipeline prompts without spending tokens.
"""

from __future__ import annotations

import os
from typing import Callable, Optional

MODEL = "claude-opus-4-8"
MAX_TOKENS = 64000


def is_dry_run() -> bool:
    return os.environ.get("J3OS_DRY_RUN", "").strip() in {"1", "true", "yes"}


def generate(
    system: str,
    prompt: str,
    *,
    dry_run: bool | None = None,
    max_tokens: int = MAX_TOKENS,
    on_text: Optional[Callable[[str], None]] = None,
) -> str:
    """Run one generation grounded in the brand knowledge system prompt.

    When ``on_text`` is provided (and not in dry-run), it is called with each
    text delta as the response streams from the API, so a caller can surface
    progress live. In dry-run mode it is called once with the full rendered
    string.
    """
    if dry_run if dry_run is not None else is_dry_run():
        text = f"[dry-run]\n--- system ---\n{system}\n--- prompt ---\n{prompt}"
        if on_text is not None:
            on_text(text)
        return text

    import anthropic

    client = anthropic.Anthropic()
    with client.messages.stream(
        model=MODEL,
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        system=[
            {
                "type": "text",
                "text": system,
                # Knowledge context is identical across pipeline stages;
                # 1h TTL keeps it warm for a whole production run.
                "cache_control": {"type": "ephemeral", "ttl": "1h"},
            }
        ],
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        chunks: list[str] = []
        for delta in stream.text_stream:
            chunks.append(delta)
            if on_text is not None:
                on_text(delta)
        message = stream.get_final_message()

    if message.stop_reason == "refusal":
        raise RuntimeError("Claude declined this request (stop_reason=refusal)")

    return "".join(chunks)
