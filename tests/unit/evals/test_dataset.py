"""Rubric dataset and responses parsing: HealthBench compatibility and validation errors."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from medagent.evals.dataset import (
    MAX_ABS_POINTS,
    RubricDatasetError,
    RubricExample,
    load_dataset,
    load_responses,
)

ROOT = Path(__file__).resolve().parents[3]
SAMPLE = ROOT / "examples" / "rubric_eval" / "safety_rubrics.jsonl"
CANARY = "Zebulon-Quartz-7781"


def _row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "prompt_id": "case-1",
        "prompt": [{"role": "user", "content": f"Question mentioning {CANARY}"}],
        "rubrics": [
            {"criterion": "Recommends emergency care", "points": 10, "tags": ["axis:accuracy"]}
        ],
        "example_tags": ["theme:emergency_referrals"],
    }
    row.update(overrides)
    return row


def _write(tmp_path: Path, *rows: Any, name: str = "data.jsonl") -> Path:
    path = tmp_path / name
    lines = [row if isinstance(row, str) else json.dumps(row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _error(tmp_path: Path, *rows: Any) -> RubricDatasetError:
    with pytest.raises(RubricDatasetError) as raised:
        load_dataset(_write(tmp_path, *rows))
    assert CANARY not in str(raised.value)
    return raised.value


def test_healthbench_row_loads_unchanged(tmp_path: Path) -> None:
    row = _row(
        prompt_id="1f548d5b-cd00-49a0-b327-283a2e00debd",
        prompt=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "reply"},
            {"role": "user", "content": "follow-up"},
        ],
        rubrics=[
            {"criterion": "a", "points": 7, "tags": ["level:example", "axis:completeness"]},
            {"criterion": "b", "points": -6, "tags": ["level:cluster", "axis:accuracy"]},
        ],
        example_tags=["theme:context_seeking", "physician_agreed_category:enough-context"],
        ideal_completions_data=None,
        canary="healthbench canary",
    )
    dataset = load_dataset(_write(tmp_path, row))
    example = dataset.examples[0]
    assert example.question == "follow-up"
    assert example.themes == ("context_seeking",)
    assert [item.axes for item in example.rubrics] == [("completeness",), ("accuracy",)]
    assert (dataset.n_criteria, dataset.n_checkable) == (2, 0)
    assert len(dataset.sha256) == 64


def test_sample_dataset_and_answers_load() -> None:
    dataset = load_dataset(SAMPLE)
    assert len(dataset.examples) == 12
    assert (dataset.n_criteria, dataset.n_checkable) == (54, 45)
    for name in ("responses_careful.jsonl", "responses_risky.jsonl"):
        answers = load_responses(SAMPLE.parent / name, dataset)
        assert list(answers) == [example.prompt_id for example in dataset.examples]


def test_blank_lines_bom_and_unicode_line_separators(tmp_path: Path) -> None:
    row = json.dumps(_row(rubrics=[{"criterion": "line\u2028sep", "points": 1}]))
    path = tmp_path / "bom.jsonl"
    path.write_bytes(b"\xef\xbb\xbf\n" + row.encode() + b"\r\n\n")
    dataset = load_dataset(path)
    assert dataset.examples[0].rubrics[0].criterion == "line\u2028sep"


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        (["{not json"], ":1: invalid JSON"),
        (["[1, 2]"], ":1: each line must be a JSON object"),
        ([_row(), _row()], ":2: duplicate prompt_id (first used on line 1)"),
        ([_row(prompt_id="bad id")], "prompt_id"),
        ([_row(prompt=[])], "prompt"),
        ([_row(rubrics=[])], "rubrics"),
        ([_row(prompt=[{"role": "assistant", "content": CANARY}])], "end with a user message"),
        ([_row(prompt=[{"role": "robot", "content": CANARY}])], "prompt[0].role"),
        ([_row(rubrics=[{"criterion": "", "points": 1}])], "rubrics[0].criterion"),
        ([_row(rubrics=[{"criterion": "c", "points": True}])], "points must be a number"),
        ([_row(rubrics=[{"criterion": "c", "points": "5"}])], "points must be a number"),
        ([_row(rubrics=[{"criterion": "c", "points": MAX_ABS_POINTS + 1}])], "within ±100"),
        ([_row(rubrics=[{"criterion": "c", "points": 1, "extra": 1}])], "rubrics[0].<unknown>"),
        ([_row(rubrics=[{"criterion": "c", "points": 1, CANARY: 1}])], "Extra inputs"),
        ([_row(rubrics=[{"criterion": "c", "points": 1, "tags": ["a b"]}])], "without whitespace"),
        ([_row(example_tags=["theme:x", "theme:x"])], "tags must be unique"),
    ],
)
def test_invalid_rows_name_line_and_field_without_echoing_text(
    tmp_path: Path, rows: list[Any], expected: str
) -> None:
    assert expected in str(_error(tmp_path, *rows))


@pytest.mark.parametrize(
    ("check", "expected"),
    [
        ({"type": "telepathy"}, "check"),
        ({"type": CANARY}, "unknown check type (expected one of: pattern,"),
        ({"type": "pattern", "any_of": [f"(?P<{CANARY}>a)"]}, "not a valid regular expression"),
        ({"type": "pattern"}, "needs any_of, all_of or none_of"),
        ({"type": "pattern", "any_of": ["(unclosed"]}, "not a valid regular expression"),
        ({"type": "pattern", "any_of": [""]}, "pattern 0 must be 1-300 characters"),
        ({"type": "length"}, "needs min_words and/or max_words"),
        ({"type": "length", "min_words": 9, "max_words": 3}, "must not exceed"),
        ({"type": "disclaimer", "surprise": True}, "check.disclaimer.<unknown>"),
    ],
)
def test_invalid_check_specs_are_rejected(
    tmp_path: Path, check: dict[str, Any], expected: str
) -> None:
    rows = [_row(rubrics=[{"criterion": "c", "points": 1, "check": check}])]
    assert expected in str(_error(tmp_path, *rows))


def test_oversized_integers_are_validation_errors_not_crashes(tmp_path: Path) -> None:
    rows = [_row(rubrics=[{"criterion": "c", "points": 10**400}])]
    assert "within ±100" in str(_error(tmp_path, *rows))
    huge = '{"prompt_id": "a", "points": ' + "9" * 5000 + "}"
    assert ":1: " in str(_error(tmp_path, huge))


def test_file_level_errors(tmp_path: Path) -> None:
    assert "no examples found" in str(_error(tmp_path, ""))
    with pytest.raises(RubricDatasetError, match="cannot read file"):
        load_dataset(tmp_path / "missing.jsonl")
    latin1 = tmp_path / "latin1.jsonl"
    latin1.write_bytes(b"\xff\xfe\x00")
    with pytest.raises(RubricDatasetError, match="not valid UTF-8"):
        load_dataset(latin1)


def test_responses_validation(tmp_path: Path) -> None:
    dataset = load_dataset(_write(tmp_path, _row()))
    ok = _write(tmp_path, {"prompt_id": "case-1", "response": "x", "usage": {}}, name="ok.jsonl")
    assert load_responses(ok, dataset) == {"case-1": "x"}
    cases = {
        "unknown.jsonl": ([{"prompt_id": "other", "response": CANARY}], "not in the dataset"),
        "dup.jsonl": (
            [{"prompt_id": "case-1", "response": "a"}, {"prompt_id": "case-1", "response": "b"}],
            ":2: duplicate prompt_id",
        ),
        "type.jsonl": ([{"prompt_id": "case-1", "response": 3}], "response"),
        "empty.jsonl": ([""], "no responses found"),
    }
    for name, (rows, expected) in cases.items():
        with pytest.raises(RubricDatasetError) as raised:
            load_responses(_write(tmp_path, *rows, name=name), dataset)
        assert expected in str(raised.value)
        assert CANARY not in str(raised.value)


def test_model_validate_accepts_python_objects() -> None:
    example = RubricExample.model_validate(_row())
    assert example.rubrics[0].points == 10.0
    assert example.rubrics[0].check is None
