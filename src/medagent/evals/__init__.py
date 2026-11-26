"""HealthBench-style rubric evaluation for medagent's free-text answers.

Grades open-ended responses against physician-style rubrics instead of
multiple-choice accuracy: each example carries criteria with positive or
negative points and ``axis:`` / ``theme:`` tags (the HealthBench JSONL format),
and a criterion may add a machine-checkable ``check`` spec that the
deterministic offline grader evaluates (must / must-not patterns, disclaimer
present, clinician referral, emergency-care recommendation, no specific dose
directive, asks a clarifying question, length). Criteria without a check are
reported as ``ungraded`` and excluded from the denominator, never guessed.

Submodules:

* :mod:`medagent.evals.dataset` — typed dataset / responses format and loaders.
* :mod:`medagent.evals.grader` — deterministic rule grader.
* :mod:`medagent.evals.scoring` — HealthBench scoring, breakdowns, bootstrap CI.
* :mod:`medagent.evals.generate` — answers from medagent's offline pipeline.
* :mod:`medagent.evals.report` — JSON + Markdown reports.
* :mod:`medagent.evals.cli` — ``python -m medagent.evals`` entry point.

RESEARCH USE ONLY. A rubric score is a benchmark signal, not evidence that an
answer is clinically safe. Not FDA-cleared.
"""

from __future__ import annotations

from medagent.evals.dataset import (
    ResponseRecord,
    RubricDatasetError,
    RubricExample,
    RubricItem,
    load_dataset,
    load_responses,
)
from medagent.evals.grader import CriterionGrade, grade_response
from medagent.evals.scoring import ConfigResult, score_configuration

__all__ = [
    "ConfigResult",
    "CriterionGrade",
    "ResponseRecord",
    "RubricDatasetError",
    "RubricExample",
    "RubricItem",
    "grade_response",
    "load_dataset",
    "load_responses",
    "score_configuration",
]
