"""CLI, runner, reports and offline answer generation for the rubric evaluation."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from medagent.evals.cli import main
from medagent.evals.dataset import load_dataset
from medagent.evals.generate import build_offline_agent, example_to_query, generate_responses
from medagent.evals.runner import EvalConfigError, parse_response_source, run_evaluation

ROOT = Path(__file__).resolve().parents[3]
SAMPLE = ROOT / "examples" / "rubric_eval"
DATASET = str(SAMPLE / "safety_rubrics.jsonl")
CAREFUL = f"careful={SAMPLE / 'responses_careful.jsonl'}"
RISKY = f"risky={SAMPLE / 'responses_risky.jsonl'}"
CANARY = "Zebulon-Quartz-7781"


@pytest.fixture(autouse=True)
def _restore_root_logging() -> Iterator[None]:
    """``main`` configures logging; undo it so other tests keep their handlers and level."""
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield
    for added in [handler for handler in root.handlers if handler not in handlers]:
        root.removeHandler(added)
    root.setLevel(level)


def _run(tmp_path: Path, *extra: str) -> tuple[int, dict, str]:
    prefix = tmp_path / "report"
    code = main(["run", "--dataset", DATASET, "--output", str(prefix), *extra])
    if not prefix.with_suffix(".json").exists():
        return code, {}, ""
    report = json.loads(prefix.with_suffix(".json").read_text(encoding="utf-8"))
    return code, report, prefix.with_suffix(".md").read_text(encoding="utf-8")


def test_validate_prints_counts(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", "--dataset", DATASET, "--responses", CAREFUL]) == 0
    out = capsys.readouterr().out
    assert "12 examples, 54 criteria (45 machine-checkable, 9 ungraded)" in out
    assert "careful: 12 responses, 0 missing" in out


def test_run_grades_recorded_answers_and_writes_reports(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, report, markdown = _run(
        tmp_path, "--responses", CAREFUL, "--responses", RISKY, "--bootstrap-samples", "200"
    )
    assert code == 0
    configs = {c["label"]: c for c in report["configurations"]}
    assert configs["careful"]["overall"]["score"] == 1.0
    assert configs["risky"]["overall"]["score"] == 0.0
    assert configs["risky"]["overall"]["mean_unclipped"] < 0
    assert configs["careful"]["criteria"]["ungraded"] == 9
    assert report["dataset"]["ungraded_criteria"] == 9
    assert report["scoring"]["bootstrap_samples"] == 200
    assert "RESEARCH USE ONLY" in report["disclaimer"]
    assert "| Axis | careful | risky |" in markdown
    assert "9 criteria have no machine-checkable `check` spec" in markdown
    assert re.search(r"^careful\s+1\.000\s", capsys.readouterr().out, re.MULTILINE)


def test_run_is_reproducible(tmp_path: Path) -> None:
    first = _run(tmp_path / "a", "--responses", RISKY, "--generate-offline")[1]
    second = _run(tmp_path / "b", "--responses", RISKY, "--generate-offline")[1]
    for report in (first, second):
        report.pop("generated_at")
    assert first == second


def test_fail_under_and_no_evidence(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, report, _ = _run(
        tmp_path, "--responses", CAREFUL, "--responses", RISKY, "--fail-under", "0.5",
        "--no-evidence",
    )  # fmt: skip
    assert code == 1
    assert "below --fail-under 0.5: risky" in capsys.readouterr().err
    grades = [g for c in report["configurations"] for e in c["examples"] for g in e["grades"]]
    assert {g["evidence"] for g in grades} == {None}


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--responses", CAREFUL, "--responses", CAREFUL], "duplicate configuration label"),
        (["--responses", CAREFUL, "--seed", "-1"], "seed must be a non-negative integer"),
        (["--responses", CAREFUL, "--bootstrap-samples", "-5"], "bootstrap samples"),
        (["--responses", CAREFUL, "--confidence", "1.5"], "confidence"),
        ([], "nothing to evaluate"),
    ],
)
def test_invalid_run_settings_exit_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], args: list[str], message: str
) -> None:
    assert _run(tmp_path, *args)[0] == 2
    assert message in capsys.readouterr().err


def test_invalid_input_files_exit_2_without_echoing_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps({"prompt_id": "x", "prompt": CANARY}) + "\n", encoding="utf-8")
    assert main(["validate", "--dataset", str(bad)]) == 2
    err = capsys.readouterr().err
    assert f"{bad}:1: prompt" in err
    assert CANARY not in err
    answers = tmp_path / "answers.jsonl"
    answers.write_text(json.dumps({"prompt_id": "nope", "response": CANARY}) + "\n", "utf-8")
    assert _run(tmp_path, "--responses", f"x={answers}")[0] == 2
    assert CANARY not in capsys.readouterr().err


def test_unwritable_output_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("", encoding="utf-8")
    code = main(["run", "--dataset", DATASET, "--responses", CAREFUL,
                 "--output", str(blocker / "report")])  # fmt: skip
    assert code == 2
    assert "error: cannot write" in capsys.readouterr().err


def test_response_source_labels() -> None:
    assert parse_response_source("a.b-c=x/y.jsonl").label == "a.b-c"
    assert parse_response_source("dir/answers.v2.jsonl").label == "answers.v2"
    for spec in ("bad label=x.jsonl", "ok=", "=x.jsonl"):
        with pytest.raises(EvalConfigError):
            parse_response_source(spec)
    with pytest.raises(SystemExit):
        main(["run", "--dataset", DATASET, "--responses", "bad label=x.jsonl"])


def test_generate_writes_offline_pipeline_answers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "offline.jsonl"
    assert main(["generate", "--dataset", DATASET, "--output", str(output)]) == 0
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 12
    assert all("RESEARCH USE ONLY" in row["response"] for row in rows)
    assert "wrote 12 medagent-offline responses" in capsys.readouterr().out


def test_run_generate_offline_saves_answers_next_to_the_report(tmp_path: Path) -> None:
    code, report, _ = _run(tmp_path, "--generate-offline", "--bootstrap-samples", "0")
    assert code == 0
    assert [c["label"] for c in report["configurations"]] == ["medagent-offline"]
    assert report["configurations"][0]["overall"]["ci_low"] is None
    assert (tmp_path / "report.medagent-offline.responses.jsonl").exists()


async def test_generation_through_a_fake_llm_is_deterministic() -> None:
    dataset = load_dataset(DATASET)
    router = MagicMock(last_model_used="fake/deterministic-llm")
    hypothesis = {"label": "Acute coronary syndrome", "uncertainty_note": "Needs an ECG"}
    payload = {"hypotheses": [hypothesis]}
    router.route_differential = AsyncMock(return_value=json.dumps(payload))
    agent = build_offline_agent(router=router)
    first = await generate_responses(dataset, agent)
    assert first == await generate_responses(dataset, agent)
    assert "1. Acute coronary syndrome (Bayesian score" in first["er-chest-pain"]
    assert first["er-chest-pain"].rstrip().endswith("diagnosis, or treatment.")
    run = await run_evaluation(dataset, generate_offline=True, agent=agent, bootstrap_samples=0)
    assert run.configurations[0].label == "medagent-offline"


def test_example_to_query_uses_the_last_user_turn() -> None:
    dataset = load_dataset(DATASET)
    query = example_to_query(dataset.examples[0])
    assert query.query == dataset.examples[0].question
    assert query.session_id == "rubric-eval-er-chest-pain"
    assert query.patient_context.clinical_notes == ""


def test_debug_logging_never_contains_prompt_or_answer_text(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    dataset = tmp_path / "canary.jsonl"
    row = {
        "prompt_id": "canary",
        "prompt": [{"role": "user", "content": f"Chest pain and {CANARY} disease, call 911?"}],
        "rubrics": [{"criterion": "c", "points": 1, "check": {"type": "disclaimer"}}],
    }
    dataset.write_text(json.dumps(row) + "\n", encoding="utf-8")
    code = main(["--log-level", "DEBUG", "run", "--dataset", str(dataset), "--generate-offline",
                 "--output", str(tmp_path / "out")])  # fmt: skip
    assert code == 0
    captured = capfd.readouterr()
    assert CANARY not in captured.out + captured.err
