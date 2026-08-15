# SPDX-License-Identifier: Apache-2.0
"""Command-line interface.

Three commands, in the order someone new to the project needs them:

``demo``      generate sample data if absent, resolve it, publish, report
``generate``  write a synthetic dataset with known duplicates
``run``       resolve an existing input file
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from descramble import __version__
from descramble.config import DEFAULT_SEED, PipelineConfig
from descramble.pipeline import run_pipeline
from descramble.reader import InputError
from descramble.sampledata import generate_records, write_csv


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--warehouse",
        type=Path,
        default=None,
        metavar="DIR",
        help="directory holding the Iceberg warehouse and catalogue (default: warehouse)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="show progress logging from the linkage engine",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="descramble",
        description=(
            "Probabilistic identity resolution into an Apache Iceberg lakehouse. "
            "Resolves messy person-like records into deduplicated golden records."
        ),
    )
    parser.add_argument("--version", action="version", version=f"descramble {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser(
        "demo",
        help="generate sample data if needed, then resolve it end to end",
        description=(
            "The fastest way to see the pipeline work. Generates a synthetic dataset "
            "containing deliberate duplicates, resolves it, writes golden records to a "
            "local Iceberg table, and reports what changed."
        ),
    )
    demo.add_argument("--people", type=int, default=2000, help="distinct people to invent")
    demo.add_argument("--seed", type=int, default=DEFAULT_SEED, help="seed for reproducible output")
    demo.add_argument("--threshold", type=float, default=None, help="match probability threshold")
    _add_common(demo)

    generate = sub.add_parser(
        "generate",
        help="write a synthetic dataset with known duplicates",
    )
    generate.add_argument("--people", type=int, default=2000, help="distinct people to invent")
    generate.add_argument(
        "--duplicate-rate",
        type=float,
        default=0.30,
        help="fraction of people who appear more than once (default: 0.30)",
    )
    generate.add_argument("--seed", type=int, default=DEFAULT_SEED, help="seed for reproducible output")
    generate.add_argument(
        "--output",
        type=Path,
        default=Path("data/sample_records.csv"),
        help="where to write the CSV (default: data/sample_records.csv)",
    )

    run = sub.add_parser("run", help="resolve an existing input file")
    run.add_argument("--input", type=Path, default=None, metavar="FILE", help="CSV or Parquet input")
    run.add_argument("--threshold", type=float, default=None, help="match probability threshold")
    run.add_argument(
        "--no-write",
        action="store_true",
        help="resolve and report without writing to the lakehouse",
    )
    run.add_argument(
        "--incremental",
        action="store_true",
        help="process only records newer than the stored watermark, and append",
    )
    _add_common(run)

    return parser


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(message)s",
        stream=sys.stderr,
    )


def _report(title: str, lines: list[str]) -> None:
    print()
    print(title)
    print("-" * len(title))
    for line in lines:
        print(f"  {line}")
    print()


def _do_generate(args: argparse.Namespace) -> int:
    rows, summary = generate_records(
        people=args.people, duplicate_rate=args.duplicate_rate, seed=args.seed
    )
    destination = write_csv(rows, args.output)
    variations = ", ".join(f"{name} {count:,}" for name, count in summary.variations_applied.items())
    _report(
        f"Generated {destination}",
        [
            f"{summary.total_rows:,} rows describing {summary.distinct_people:,} people",
            f"{summary.people_with_duplicates:,} people appear more than once "
            f"({summary.duplicate_rows:,} duplicate rows)",
            f"a perfect resolver would produce {summary.expected_golden_records:,} golden records",
            f"variations applied: {variations}",
        ],
    )
    return 0


def _do_run(args: argparse.Namespace, config: PipelineConfig) -> int:
    result = run_pipeline(
        config,
        write=not getattr(args, "no_write", False),
        incremental=getattr(args, "incremental", False),
    )
    if result.input_records == 0:
        _report("Nothing to do", ["no records newer than the stored watermark"])
        return 0
    _report("Resolution complete", result.summary_lines())
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _configure_logging(getattr(args, "verbose", False))

    config = PipelineConfig.from_environment().with_overrides(
        warehouse_dir=getattr(args, "warehouse", None),
        match_threshold=getattr(args, "threshold", None),
        seed=getattr(args, "seed", None) if args.command != "generate" else None,
        input_path=getattr(args, "input", None),
    )

    try:
        if args.command == "generate":
            return _do_generate(args)

        if args.command == "demo":
            if not config.input_path.exists():
                rows, summary = generate_records(people=args.people, seed=args.seed)
                write_csv(rows, config.input_path)
                _report(
                    f"Generated {config.input_path}",
                    [
                        f"{summary.total_rows:,} rows describing {summary.distinct_people:,} people",
                        f"a perfect resolver would produce "
                        f"{summary.expected_golden_records:,} golden records",
                    ],
                )
            else:
                print(f"Using existing input at {config.input_path}")
            return _do_run(args, config)

        return _do_run(args, config)

    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
