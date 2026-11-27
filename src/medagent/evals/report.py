"""JSON and Markdown reports for rubric evaluation runs.

The JSON report is the complete, machine-readable record (every criterion's
verdict, grader, reason and, unless disabled, a short evidence excerpt); the
Markdown report is the human-readable summary with per-axis and per-theme
tables and the criteria that cost points. Both disclose how many criteria were
ungraded and therefore excluded from the denominators.

Reports quote dataset criteria and short excerpts of the graded answers, so
treat them like the inputs: use synthetic, PHI-free datasets (SAFETY.md).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from medagent.evals.grader import MET, NOT_MET, UNGRADED
from medagent.evals.runner import EvalRun
from medagent.evals.scoring import Aggregate, ConfigResult

REPORT_VERSION = "1.0"
DISCLAIMER = (
    "RESEARCH USE ONLY. Rubric scores are benchmark signals from heuristic, rule-based "
    "graders; they are not evidence that an answer is clinically safe. medagent-core is "
    "not FDA-cleared and must not guide clinical decisions."
)
FORMULA = (
    "per example: sum of points of met criteria / sum of positive points, over graded "
    "criteria only (ungraded criteria are excluded from both sums); aggregate: mean of "
    "example scores clipped to [0, 1] with a seeded percentile bootstrap CI"
)


def _dataset_summary(run: EvalRun) -> dict[str, Any]:
    dataset = run.dataset
    return {
        "source": dataset.source,
        "sha256": dataset.sha256,
        "examples": len(dataset.examples),
        "criteria": dataset.n_criteria,
        "checkable_criteria": dataset.n_checkable,
        "ungraded_criteria": dataset.n_criteria - dataset.n_checkable,
    }


def report_dict(run: EvalRun, *, include_evidence: bool = True) -> dict[str, Any]:
    """Return the JSON report as a dictionary.

    Args:
        run: The evaluation run.
        include_evidence: Keep the matched answer excerpts; ``False`` sets every
            ``evidence`` field to ``None``.

    Returns:
        A JSON-serialisable dictionary (``report_version`` 1.0).
    """
    configurations = [config.to_dict() for config in run.configurations]
    if not include_evidence:
        for config in configurations:
            for example in config["examples"]:
                for grade in example["grades"]:
                    grade["evidence"] = None
    return {
        "report_version": REPORT_VERSION,
        "generated_at": run.generated_at.isoformat(timespec="seconds"),
        "disclaimer": DISCLAIMER,
        "dataset": _dataset_summary(run),
        "scoring": {
            "formula": FORMULA,
            "grader": run.grader,
            "bootstrap_samples": run.bootstrap_samples,
            "seed": run.seed,
            "confidence": run.confidence,
        },
        "configurations": configurations,
    }


def _cell(text: object) -> str:
    """Make ``text`` safe inside a Markdown table cell."""
    return " ".join(str(text).split()).replace("|", "\\|")


def _num(value: float | None, digits: int = 3) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _interval(agg: Aggregate) -> str:
    if agg.ci_low is None or agg.ci_high is None:
        return "n/a"
    return f"{agg.ci_low:.3f}–{agg.ci_high:.3f}"


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def _summary_rows(run: EvalRun) -> list[str]:
    level = f"{run.confidence:.0%}"
    rows = [
        f"| Configuration | Score | {level} CI | Bootstrap std | Examples scored "
        "| Criteria met / graded | Ungraded | Positive points graded |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for config in run.configurations:
        graded = config.count(MET) + config.count(NOT_MET)
        rows.append(
            f"| {_cell(config.label)} | {_num(config.overall.score)} "
            f"| {_interval(config.overall)} | {_num(config.overall.bootstrap_std)} "
            f"| {config.overall.n}/{config.n_examples} | {config.count(MET)}/{graded} "
            f"| {config.count(UNGRADED)} | {_percent(config.coverage)} |"
        )
    return rows


def _breakdown_rows(run: EvalRun, kind: str) -> list[str]:
    names = sorted({name for config in run.configurations for name in getattr(config, kind)})
    if not names:
        return []
    labels = [_cell(config.label) for config in run.configurations]
    header = {"axes": "Axis", "themes": "Theme"}[kind]
    rows = [
        f"| {header} | " + " | ".join(labels) + " |",
        "|---|" + "---:|" * len(labels),
    ]
    for name in names:
        cells = []
        for config in run.configurations:
            agg = getattr(config, kind).get(name)
            cells.append("n/a" if agg is None else f"{_num(agg.score)} (n={agg.n})")
        rows.append(f"| {_cell(name)} | " + " | ".join(cells) + " |")
    return rows


def _points_lost_rows(config: ConfigResult) -> list[str]:
    lost = [(r.prompt_id, grade) for r in config.examples for grade in r.points_lost()]
    if not lost:
        return ["No graded criterion cost points."]
    rows = [
        "| Example | Criterion | Points | Verdict | Grader | Reason |",
        "|---|---|---:|---|---|---|",
    ]
    for prompt_id, grade in lost:
        rows.append(
            f"| {_cell(prompt_id)} | {_cell(grade.criterion)} | {grade.points:g} "
            f"| {grade.verdict} | {_cell(grade.grader or '')} | {_cell(grade.reason)} |"
        )
    return rows


def _ungraded_rows(run: EvalRun) -> list[str]:
    items = [
        (example.prompt_id, item)
        for example in run.dataset.examples
        for item in example.rubrics
        if item.check is None
    ]
    if not items:
        return ["Every criterion is machine-checkable; nothing was excluded."]
    rows = [
        f"{len(items)} criteria have no machine-checkable `check` spec. They are reported as "
        "`ungraded`, never counted as met or unmet, and excluded from both sums of the "
        "score; grade them by hand or add a `check`.",
        "",
        "| Example | Criterion | Points |",
        "|---|---|---:|",
    ]
    rows.extend(
        f"| {_cell(prompt_id)} | {_cell(item.criterion)} | {item.points:g} |"
        for prompt_id, item in items
    )
    return rows


def render_markdown(run: EvalRun) -> str:
    """Render the human-readable Markdown report.

    Args:
        run: The evaluation run.

    Returns:
        Markdown text ending with a newline.
    """
    summary = _dataset_summary(run)
    lines = [
        "# medagent rubric evaluation report",
        "",
        f"> {DISCLAIMER}",
        "",
        f"- **Dataset:** `{_cell(summary['source'])}` (sha256 `{summary['sha256'][:12]}`), "
        f"{summary['examples']} examples, {summary['criteria']} criteria "
        f"({summary['checkable_criteria']} machine-checkable, "
        f"{summary['ungraded_criteria']} ungraded)",
        f"- **Grader:** {run.grader} (deterministic, offline)",
        f"- **Score:** {FORMULA}; {run.bootstrap_samples} bootstrap resamples, "
        f"seed {run.seed}, confidence {run.confidence:g}",
        f"- **Generated:** {run.generated_at.isoformat(timespec='seconds')}",
        "",
        "## Summary",
        "",
        *_summary_rows(run),
    ]
    for kind, title in (("axes", "By axis"), ("themes", "By theme")):
        rows = _breakdown_rows(run, kind)
        if rows:
            lines += ["", f"## {title}", "", *rows]
    for config in run.configurations:
        lines += ["", f"## Points lost: {_cell(config.label)}", ""]
        lines.append(f"Source: `{_cell(config.source)}`")
        if config.missing:
            lines.append(f"Missing responses (excluded): {', '.join(config.missing)}")
        if config.unscorable:
            lines.append(
                "Unscorable (no graded positive points, excluded): " + ", ".join(config.unscorable)
            )
        lines += ["", *_points_lost_rows(config)]
    lines += ["", "## Ungraded criteria", "", *_ungraded_rows(run)]
    return "\n".join(lines) + "\n"


def render_console(run: EvalRun) -> str:
    """Render a compact plain-text summary for the terminal.

    Args:
        run: The evaluation run.

    Returns:
        Fixed-width text, one row per configuration.
    """
    summary = _dataset_summary(run)
    width = max([13, *(len(config.label) for config in run.configurations)])
    level = f"{run.confidence:.0%} CI"
    lines = [
        f"{summary['examples']} examples, {summary['criteria']} criteria "
        f"({summary['ungraded_criteria']} ungraded: excluded from the denominators)",
        f"{'configuration':<{width}}  score  {level:<13}  met/graded  ungraded  missing",
    ]
    for config in run.configurations:
        graded = config.count(MET) + config.count(NOT_MET)
        interval = (
            f"[{config.overall.ci_low:.3f}, {config.overall.ci_high:.3f}]"
            if config.overall.ci_low is not None and config.overall.ci_high is not None
            else "n/a"
        )
        lines.append(
            f"{config.label:<{width}}  {_num(config.overall.score):<5}  {interval:<13}  "
            f"{f'{config.count(MET)}/{graded}':<10}  {config.count(UNGRADED):<8}  "
            f"{len(config.missing)}"
        )
    return "\n".join(lines)


def write_reports(
    run: EvalRun, prefix: str | Path, *, include_evidence: bool = True
) -> tuple[Path, Path]:
    """Write ``<prefix>.json`` and ``<prefix>.md`` (parent directories are created).

    Args:
        run: The evaluation run.
        prefix: Output path without extension, e.g. ``results/rubric_eval``.
        include_evidence: Keep answer excerpts in the JSON report.

    Returns:
        ``(json_path, markdown_path)``.
    """
    base = Path(prefix)
    base.parent.mkdir(parents=True, exist_ok=True)
    json_path = base.with_name(base.name + ".json")
    markdown_path = base.with_name(base.name + ".md")
    payload = report_dict(run, include_evidence=include_evidence)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", "utf-8")
    markdown_path.write_text(render_markdown(run), "utf-8")
    return json_path, markdown_path


def write_responses(responses: Mapping[str, str], path: str | Path) -> Path:
    """Write answers as a responses JSONL file that ``--responses`` can grade again.

    Args:
        responses: ``prompt_id`` → answer text.
        path: Output file.

    Returns:
        The written path.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = (
        json.dumps({"prompt_id": prompt_id, "response": text}, ensure_ascii=False)
        for prompt_id, text in responses.items()
    )
    target.write_text("\n".join(rows) + "\n", "utf-8")
    return target
