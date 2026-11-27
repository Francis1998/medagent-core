"""HealthBench-style rubric evaluation of free-text answers.

Thin wrapper around ``python -m medagent.evals`` (see
docs/guides/RUBRIC_EVAL_GUIDE.md), next to the MCQ (eval_medqa.py) and
interaction (eval_drugbank.py) benchmarks. Grades recorded answers and/or
answers from medagent's offline pipeline against physician-style rubrics and
writes JSON + Markdown reports.

Usage:
    python scripts/eval_rubric.py run \
        --dataset examples/rubric_eval/safety_rubrics.jsonl \
        --responses careful=examples/rubric_eval/responses_careful.jsonl \
        --generate-offline \
        --output results/rubric_eval

Runs offline: no LLM keys, network access or GPU needed. RESEARCH USE ONLY.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from medagent.evals.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
