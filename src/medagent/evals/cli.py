"""``python -m medagent.evals`` — rubric evaluation from the command line.

Subcommands:

* ``validate`` — check a dataset (and optional responses files) and print counts.
* ``generate`` — answer a dataset with medagent's offline pipeline and write a
  responses JSONL file.
* ``run`` — grade recorded and/or generated answers, print a summary and write
  JSON + Markdown reports.

Exit codes: 0 success; 1 a configuration scored below ``--fail-under``;
2 invalid arguments or input files. Errors name the file, line and field but
never echo dataset or answer text, and nothing is logged about them.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

from medagent.evals.dataset import RubricDataset, RubricDatasetError, load_dataset, load_responses
from medagent.evals.runner import (
    EvalConfigError,
    ResponseSource,
    parse_response_source,
    run_evaluation,
)
from medagent.evals.scoring import DEFAULT_BOOTSTRAP_SAMPLES, DEFAULT_CONFIDENCE, DEFAULT_SEED
from medagent.logging_config import configure_logging

DEFAULT_OUTPUT = "results/rubric_eval"
EXIT_OK = 0
EXIT_BELOW_THRESHOLD = 1
EXIT_INPUT_ERROR = 2
RESEARCH_NOTICE = "RESEARCH USE ONLY: rubric scores are benchmark signals, not safety evidence."


def _source(value: str) -> ResponseSource:
    try:
        return parse_response_source(value)
    except EvalConfigError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def _unit_interval(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number") from None
    if not 0.0 <= number <= 1.0:
        raise argparse.ArgumentTypeError(f"{value!r} is not within [0, 1]")
    return number


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m medagent.evals",
        description=(
            "HealthBench-style rubric evaluation of free-text answers (RESEARCH USE ONLY)."
        ),
    )
    parser.add_argument(
        "--log-level",
        type=str.upper,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="ERROR",
        help="stderr log level for the medagent pipeline (default: ERROR)",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    def dataset_arg(sub: argparse.ArgumentParser) -> None:
        sub.add_argument(
            "--dataset", required=True, type=Path, help="rubric dataset (HealthBench JSONL)"
        )

    validate = commands.add_parser("validate", help="validate a dataset and responses files")
    dataset_arg(validate)
    validate.add_argument(
        "--responses",
        action="append",
        default=[],
        type=_source,
        metavar="[LABEL=]PATH",
        help="responses JSONL to validate against the dataset (repeatable)",
    )

    generate = commands.add_parser(
        "generate", help="answer the dataset with medagent's offline pipeline"
    )
    dataset_arg(generate)
    generate.add_argument(
        "--output", required=True, type=Path, help="responses JSONL file to write"
    )

    run = commands.add_parser("run", help="grade answers and write JSON + Markdown reports")
    dataset_arg(run)
    run.add_argument(
        "--responses",
        action="append",
        default=[],
        type=_source,
        metavar="[LABEL=]PATH",
        help="pre-recorded responses JSONL, one configuration each (repeatable)",
    )
    run.add_argument(
        "--generate-offline",
        action="store_true",
        help="also answer the dataset with medagent's offline pipeline (medagent-offline)",
    )
    run.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"report path without extension (default: {DEFAULT_OUTPUT})",
    )
    run.add_argument(
        "--bootstrap-samples",
        type=int,
        default=DEFAULT_BOOTSTRAP_SAMPLES,
        help=f"bootstrap resamples, 0 disables the CI (default: {DEFAULT_BOOTSTRAP_SAMPLES})",
    )
    run.add_argument(
        "--seed", type=int, default=DEFAULT_SEED, help=f"bootstrap seed (default: {DEFAULT_SEED})"
    )
    run.add_argument(
        "--confidence",
        type=float,
        default=DEFAULT_CONFIDENCE,
        help=f"confidence level of the interval (default: {DEFAULT_CONFIDENCE})",
    )
    run.add_argument(
        "--no-evidence",
        action="store_true",
        help="omit matched answer excerpts from the JSON report",
    )
    run.add_argument(
        "--fail-under",
        type=_unit_interval,
        default=None,
        metavar="SCORE",
        help="exit 1 when any configuration's score is below SCORE (for CI gates)",
    )
    return parser


def _validate(dataset: RubricDataset, sources: Sequence[ResponseSource]) -> int:
    ungraded = dataset.n_criteria - dataset.n_checkable
    print(
        f"ok  {dataset.source}: {len(dataset.examples)} examples, {dataset.n_criteria} "
        f"criteria ({dataset.n_checkable} machine-checkable, {ungraded} ungraded)"
    )
    for source in sources:
        responses = load_responses(source.path, dataset)
        missing = len(dataset.examples) - len(responses)
        print(f"ok  {source.label}: {len(responses)} responses, {missing} missing")
    return EXIT_OK


def _generate(dataset: RubricDataset, output: Path) -> int:
    from medagent.evals.generate import generate_responses
    from medagent.evals.report import write_responses

    responses = asyncio.run(generate_responses(dataset))
    path = write_responses(responses, output)
    print(f"wrote {len(responses)} medagent-offline responses to {path}")
    return EXIT_OK


def _run(dataset: RubricDataset, args: argparse.Namespace) -> int:
    from medagent.evals.report import render_console, write_reports, write_responses

    run = asyncio.run(
        run_evaluation(
            dataset,
            args.responses,
            generate_offline=args.generate_offline,
            bootstrap_samples=args.bootstrap_samples,
            seed=args.seed,
            confidence=args.confidence,
        )
    )
    print(render_console(run))
    for label, responses in (run.generated_responses or {}).items():
        path = write_responses(responses, f"{args.output}.{label}.responses.jsonl")
        print(f"wrote {path}")
    evidence = not args.no_evidence
    json_path, markdown_path = write_reports(run, args.output, include_evidence=evidence)
    print(f"wrote {json_path}\nwrote {markdown_path}")
    print(RESEARCH_NOTICE)
    if args.fail_under is not None:
        failing = [
            config.label
            for config in run.configurations
            if config.overall.score is None or config.overall.score < args.fail_under
        ]
        if failing:
            print(f"below --fail-under {args.fail_under:g}: {', '.join(failing)}", file=sys.stderr)
            return EXIT_BELOW_THRESHOLD
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    """Run the rubric evaluation CLI.

    Args:
        argv: Command-line arguments; ``None`` reads ``sys.argv``.

    Returns:
        The process exit code.
    """
    args = _build_parser().parse_args(argv)
    configure_logging(args.log_level)
    try:
        dataset = load_dataset(args.dataset)
        if args.command == "validate":
            return _validate(dataset, args.responses)
        if args.command == "generate":
            return _generate(dataset, args.output)
        return _run(dataset, args)
    except (RubricDatasetError, EvalConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    except OSError as exc:
        # Report the failing path, not the message: it is the only actionable detail.
        target = exc.filename if exc.filename is not None else "an output file"
        print(f"error: cannot write {target} ({type(exc).__name__})", file=sys.stderr)
        return EXIT_INPUT_ERROR
