from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .benchmark import format_results_table, load_meta_decks, run_meta_benchmark
from .engine import extract_sdk_zip, resolve_wrapper_dir
from .paths import DEFAULT_SDK_ZIP, SIMPLE_BASELINE_AGENT


def _add_sdk_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sdk-zip", type=Path, default=None, help="Path to pokemon-tcg-ai-battle.zip")
    parser.add_argument(
        "--sdk-dir",
        type=Path,
        default=None,
        help="Path to an extracted sample_submission/sample_submission directory",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark Pokemon TCG AI Battle agents against a 10-deck meta.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser("bootstrap", help="extract and verify the user-provided Kaggle SDK")
    bootstrap.add_argument("--sdk-zip", type=Path, default=DEFAULT_SDK_ZIP)
    bootstrap.add_argument("--force", action="store_true")

    subparsers.add_parser("list-decks", help="list the registered 10-deck meta panel")

    quickstart = subparsers.add_parser("quickstart", help="run the default one-game-per-deck mini benchmark")
    _add_sdk_args(quickstart)
    quickstart.add_argument("--agent", type=Path, default=SIMPLE_BASELINE_AGENT)
    quickstart.add_argument("--max-decisions", type=int, default=1000)
    quickstart.add_argument("--label", default="quickstart")

    benchmark = subparsers.add_parser("benchmark", help="run the meta benchmark")
    _add_sdk_args(benchmark)
    benchmark.add_argument("--agent", type=Path, default=SIMPLE_BASELINE_AGENT)
    benchmark.add_argument("--matches", type=int, default=1)
    benchmark.add_argument("--max-decisions", type=int, default=1000)
    benchmark.add_argument("--label", default="benchmark")
    benchmark.add_argument("--out-dir", type=Path, default=None)

    smoke = subparsers.add_parser("smoke", help="play one full game and assert zero engine errors")
    _add_sdk_args(smoke)
    smoke.add_argument("--agent", type=Path, default=SIMPLE_BASELINE_AGENT)
    smoke.add_argument("--max-decisions", type=int, default=1000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "bootstrap":
        wrapper = extract_sdk_zip(args.sdk_zip, force=args.force)
        print(f"ENGINE_WRAPPER\t{wrapper}")
        return 0

    if args.command == "list-decks":
        print("id\tweight\tarchetype\tname")
        for deck in load_meta_decks():
            print(f"{deck.deck_id}\t{deck.weight:.1f}\t{deck.archetype}\t{deck.name}")
        return 0

    if args.command == "quickstart":
        rows, out_dir = run_meta_benchmark(
            agent=args.agent,
            sdk_dir=args.sdk_dir,
            sdk_zip=args.sdk_zip,
            matches=1,
            max_decisions=args.max_decisions,
            label=args.label,
        )
        print(f"RUN_DIR\t{out_dir}")
        print(format_results_table(rows))
        return 0

    if args.command == "benchmark":
        rows, out_dir = run_meta_benchmark(
            agent=args.agent,
            sdk_dir=args.sdk_dir,
            sdk_zip=args.sdk_zip,
            matches=args.matches,
            max_decisions=args.max_decisions,
            label=args.label,
            out_dir=args.out_dir,
        )
        print(f"RUN_DIR\t{out_dir}")
        print(format_results_table(rows))
        return 0

    if args.command == "smoke":
        resolve_wrapper_dir(sdk_dir=args.sdk_dir, sdk_zip=args.sdk_zip)
        rows, out_dir = run_meta_benchmark(
            agent=args.agent,
            sdk_dir=args.sdk_dir,
            sdk_zip=args.sdk_zip,
            matches=1,
            max_decisions=args.max_decisions,
            label="smoke",
            forced_first_player=0,
            deck_limit=1,
        )
        print(f"RUN_DIR\t{out_dir}")
        print(format_results_table(rows))
        return 0

    print(f"Unhandled command: {args.command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
