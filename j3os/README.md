# J3OS — the J3 Labs Operating System

J3OS is an integrated platform for launching, operating, and scaling premium
brands from a shared operating system, while each brand keeps its own
identity, voice, and creative direction.

**Glass & Counsel™** is the first company that runs on it — the reference
implementation and proving ground. Once the architecture is validated, the
same engines can power Launchly, Praxis, Paranormal Gaia, J3P0_DEV, and
future J3 Labs ventures with minimal duplication.

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

## The first two embedded systems

### System 01 — Brand Knowledge Engine (`j3os/engines/knowledge/`)

The brain. It stores each brand's permanent source of truth — Brand Bible,
ICPs, editorial guidelines, creative direction, commerce rules, AI
instructions, and roadmap — as versioned markdown under
`j3os/brands/<slug>/knowledge/`. Every AI workflow starts here.

### System 02 — Editorial Production Engine (`j3os/engines/editorial/`)

The factory. One topic goes in; a full multi-channel asset kit comes out:

```
Research → Editorial Brief → SEO Outline → Long-form Article
→ Newsletter → Instagram Carousel → Pinterest Pins → Amazon Review
→ Email → Hero Images → Scheduling Queue
```

Every asset references the Knowledge Engine before generation: the assembled
brand context is the (cached) system prompt for every stage, and each stage
builds on the artifacts produced before it.

## Quick start

```bash
pip install -r j3os/requirements.txt

# Inspect the OS
python -m j3os brands
python -m j3os engines
python -m j3os knowledge glass-and-counsel
python -m j3os knowledge glass-and-counsel --doc 03_ICP

# Preview pipeline prompts without spending tokens
python -m j3os editorial glass-and-counsel \
    --topic "The 5-minute desk reset for associates" --dry-run

# Full production run (needs ANTHROPIC_API_KEY)
python -m j3os editorial glass-and-counsel \
    --topic "The 5-minute desk reset for associates"

# Or a subset of stages
python -m j3os editorial glass-and-counsel \
    --topic "Worth It? The glass desk mat" --stages research,brief,article
```

Artifacts are written to `j3os/brands/<slug>/output/<timestamp>-<topic>/`,
one markdown file per stage, plus a `manifest.json` describing the run.

## Live console

```bash
python -m j3os serve            # → http://127.0.0.1:8300
```

A web console that runs the pipeline for real and streams every stage's
output to the browser token-by-token over Server-Sent Events. With
`ANTHROPIC_API_KEY` set the console runs live; without it, it falls back
to dry-run mode (rendering the grounded prompts only). Views: Production
(run + live timeline), Knowledge (browse/search the brand docs), and Runs
(replay any past run's event stream).

## Grading & batch production

```bash
# Grade the latest run against the editorial standards (04_EDITORIAL.md)
python -m j3os grade glass-and-counsel

# Web-search-grounded research stage (live key required)
python -m j3os editorial glass-and-counsel \
    --topic "The 5-minute desk reset for associates" --web

# Run a whole content calendar via the Batches API (50% cost;
# falls back to dry-run without a key)
python -m j3os batch glass-and-counsel \
    --calendar j3os/brands/glass-and-counsel/calendar.example.json
```

`grade` scores each stage against the brand's editorial guidelines and writes
a `scorecard.md` plus `scores.json` into the run's `review/` folder. `batch`
fans a calendar of topics through the pipeline in one Batches API job.

## Tests

```bash
python -m pytest j3os/tests -q
```

All tests run offline (dry-run mode).

## Adding a new brand

1. Create `j3os/brands/<slug>/knowledge/` with the canonical docs
   (`00_PROJECT.md` … `08_ROADMAP.md` — copy the Glass & Counsel set as a
   template).
2. `python -m j3os brands` — the brand is discovered automatically.
3. Run any engine against it. That's the whole point of the OS.

## Roadmap

The remaining engines (brand, design, commerce, automation, analytics,
AI studio, research) are registered as planned stubs with defined contracts.
See `docs/J3OS_ORCHESTRATION_PLAN.md` for the phased build loop.
