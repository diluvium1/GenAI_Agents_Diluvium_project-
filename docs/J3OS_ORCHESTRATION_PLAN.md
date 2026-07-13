# J3OS Orchestration Plan

How the J3 Labs repo gets built out, iteration by iteration. Each loop
iteration is: **pick the next milestone → build → test offline → run one
live generation → commit → push → review output quality → feed learnings
back into the knowledge base.**

We are not building Glass & Counsel. We are building the first reference
implementation of the **J3 Operating System (J3OS)**. Glass & Counsel is
simply the first company that runs on it.

## Architecture

```
                    J3OS
                     │
    ┌────────────────┼────────────────┐
    │                │                │
 Brand Engine   Editorial Engine   Commerce Engine
    │                │                │
 Design Engine  Knowledge Engine  Automation Engine
    │                │                │
        Analytics + AI Studio + Research
```

Every future company plugs into this. Shared core (`j3os/core/`), pluggable
engines (`j3os/engines/`), and per-brand knowledge (`j3os/brands/<slug>/`).

## Loop 1 — Foundation ✅ (this upgrade)

- [x] Canonical Glass & Counsel knowledge base (`00_PROJECT` … `08_ROADMAP`)
- [x] Core: `Brand`, `Engine` contract, `EngineRegistry`, shared Claude client
      (Opus 4.8, adaptive thinking, streaming, 1h prompt caching on the
      knowledge context)
- [x] System 01 — Brand Knowledge Engine (load / get / search / context block)
- [x] System 02 — Editorial Production Engine (11-stage pipeline, artifacts
      written per stage, dry-run mode)
- [x] CLI (`python -m j3os`), offline test suite, planned-engine stubs

## Loop 2 — Editorial hardening

- [x] Live web console (`python -m j3os serve`): FastAPI + SSE streaming of
      pipeline runs, with per-stage progress events and `manifest.json`
- [ ] Live pipeline run for 3 real Glass & Counsel topics; grade outputs
      against `04_EDITORIAL.md` and tighten stage instructions
- [ ] Structured artifact metadata (JSON sidecars: keywords, products,
      channel targets) so downstream automation can consume the kit
- [ ] Web-search-grounded research stage (server-side `web_search` tool)
- [ ] Batch mode: run a content calendar (N topics) through the Batches API
      at 50% cost

## Loop 3 — Commerce + Automation (Phase 2 engines)

- [ ] Commerce Engine: product catalog per brand, Amazon Associates link
      formatting, disclosure blocks injected into every commerce artifact
- [ ] Automation Engine: turn `scheduling_queue` artifacts into real queue
      entries (start with a local queue file; integrations later)
- [ ] Brand Engine: new-brand bootstrap (`j3os brand new <slug>`) that
      interviews for the 9 canonical docs

## Loop 4 — Design + Analytics (Phase 2/3)

- [ ] Design Engine: hero-image prompts → actual image generation workflow
- [ ] Analytics Engine: per-artifact performance log, content scoring
- [ ] AI Studio: interactive session grounded in the knowledge context
- [ ] Research Engine: standing trend research that writes back into
      `knowledge/` as dated research memos

## Loop 5 — Multi-brand validation

- [ ] Onboard a second brand (Launchly or Praxis) using only the documented
      "Adding a new brand" flow — zero code changes is the success criterion
- [ ] Extract anything brand-specific that leaked into engines back into
      knowledge docs

## Operating rules

1. Every engine reads the Knowledge Engine before generating anything
   (codified in each brand's `07_AI.md`).
2. Engines never hardcode brand facts — if it's about the brand, it lives
   in `knowledge/`.
3. Everything ships with offline tests; live API calls are opt-in.
4. Output quality feedback loops back into the knowledge docs, not into
   prompt hacks inside engines.
