"""J3OS command-line interface.

Usage:
    python -m j3os brands
    python -m j3os engines
    python -m j3os knowledge glass-and-counsel [--doc 03_ICP] [--search term]
    python -m j3os editorial glass-and-counsel --topic "..." [--stages a,b] [--dry-run]
"""

from __future__ import annotations

import argparse
import sys

from j3os.core.brand import Brand, discover_brands
from j3os.core.engine import default_registry
from j3os.engines.editorial.pipeline import STAGE_KEYS
from j3os.engines.knowledge.engine import KnowledgeEngine


def cmd_brands(_: argparse.Namespace) -> int:
    brands = discover_brands()
    if not brands:
        print("No brands installed.")
        return 1
    for b in brands:
        docs = len(list(b.knowledge_dir.glob("*.md")))
        print(f"{b.slug:24} {b.display_name}  ({docs} knowledge docs)")
    return 0


def cmd_engines(_: argparse.Namespace) -> int:
    for engine in default_registry().all():
        print(f"[{engine.status:7}] {engine.name:12} {engine.description}")
    return 0


def cmd_knowledge(args: argparse.Namespace) -> int:
    brand = Brand.load(args.brand)
    engine = KnowledgeEngine()
    if args.doc:
        print(engine.get(brand, args.doc).content)
    elif args.search:
        hits = engine.search(brand, args.search)
        if not hits:
            print(f"No knowledge docs match '{args.search}'.")
            return 1
        for doc in hits:
            print(f"{doc.name:20} {doc.title}")
    else:
        for doc in engine.load(brand):
            print(f"{doc.name:20} {doc.title}")
    return 0


def cmd_editorial(args: argparse.Namespace) -> int:
    from j3os.engines.editorial.pipeline import run_pipeline

    brand = Brand.load(args.brand)
    stages = args.stages.split(",") if args.stages else None
    result = run_pipeline(brand, args.topic, stages=stages, dry_run=args.dry_run)
    print(f"Wrote {len(result.artifacts)} artifacts to {result.output_dir}")
    for key in result.artifacts:
        print(f"  - {key}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="j3os", description="J3OS — the J3 Labs operating system")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("brands", help="List installed brands").set_defaults(func=cmd_brands)
    sub.add_parser("engines", help="List engines and their status").set_defaults(func=cmd_engines)

    p_know = sub.add_parser("knowledge", help="Inspect a brand's knowledge base")
    p_know.add_argument("brand")
    p_know.add_argument("--doc", help="Print one document by stem, e.g. 03_ICP")
    p_know.add_argument("--search", help="Full-text search the knowledge base")
    p_know.set_defaults(func=cmd_knowledge)

    p_ed = sub.add_parser("editorial", help="Run the editorial production pipeline")
    p_ed.add_argument("brand")
    p_ed.add_argument("--topic", required=True)
    p_ed.add_argument(
        "--stages",
        help=f"Comma-separated subset of stages. Valid: {','.join(STAGE_KEYS)}",
    )
    p_ed.add_argument(
        "--dry-run",
        action="store_true",
        help="Render prompts without calling the Claude API",
    )
    p_ed.set_defaults(func=cmd_editorial)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
