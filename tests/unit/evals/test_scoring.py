"""HealthBench scoring: formula, negative points, clipping, ungraded criteria, bootstrap CI."""

from __future__ import annotations

from typing import Any

import pytest

from medagent.evals.dataset import RubricDataset, RubricExample
from medagent.evals.grader import MET, NOT_MET, UNGRADED, CriterionGrade, Verdict
from medagent.evals.scoring import (
    aggregate,
    bootstrap_interval,
    score_configuration,
    score_example,
)


def _grade(points: float, verdict: Verdict, *tags: str) -> CriterionGrade:
    grader = None if verdict == UNGRADED else "rule:pattern"
    return CriterionGrade(0, "c", points, tags, verdict, grader, "test")


def _example(prompt_id: str = "p", points: tuple[float, ...] = (1,), theme: str = "t") -> Any:
    return RubricExample.model_validate(
        {
            "prompt_id": prompt_id,
            "prompt": [{"role": "user", "content": "q"}],
            "rubrics": [{"criterion": f"c{i}", "points": p} for i, p in enumerate(points)],
            "example_tags": [f"theme:{theme}"],
        }
    )


def test_score_is_met_points_over_positive_points_including_negative_criteria() -> None:
    grades = [_grade(10, MET), _grade(5, NOT_MET), _grade(-8, MET), _grade(-3, NOT_MET)]
    result = score_example(_example(points=(10, 5, -8, -3)), grades)
    assert result.score == pytest.approx((10 - 8) / 15)
    assert (result.achieved_points, result.graded_positive_points) == (2, 15)
    assert [g.points for g in result.points_lost()] == [5, -8]


def test_example_scores_are_not_clipped_but_the_aggregate_is() -> None:
    result = score_example(_example(points=(5, -8)), [_grade(5, NOT_MET), _grade(-8, MET)])
    assert result.score == pytest.approx(-1.6)
    agg = aggregate([-1.6, 0.4], bootstrap_samples=0)
    assert agg.mean == pytest.approx(-0.6)
    assert agg.score == 0.0
    assert aggregate([1.0, 1.0], bootstrap_samples=0).score == 1.0


def test_ungraded_criteria_are_excluded_from_both_sums_and_disclosed() -> None:
    grades = [_grade(10, MET), _grade(10, UNGRADED), _grade(-5, UNGRADED)]
    result = score_example(_example(points=(10, 10, -5)), grades)
    assert result.score == 1.0
    assert (result.graded_positive_points, result.total_positive_points) == (10, 20)
    assert result.count(UNGRADED) == 2


def test_examples_without_graded_positive_points_are_unscorable() -> None:
    only_negative = score_example(_example(points=(-5,)), [_grade(-5, NOT_MET)])
    all_ungraded = score_example(_example(points=(5,)), [_grade(5, UNGRADED)])
    assert only_negative.score is None
    assert all_ungraded.score is None


def test_axis_scores_use_criteria_tagged_with_the_axis() -> None:
    grades = [
        _grade(4, MET, "axis:accuracy"),
        _grade(4, NOT_MET, "axis:accuracy", "axis:completeness"),
        _grade(-2, MET, "axis:completeness"),
    ]
    result = score_example(_example(points=(4, 4, -2)), grades)
    assert result.axis_scores == {"accuracy": 0.5, "completeness": -0.5}


def _dataset(*examples: Any) -> RubricDataset:
    return RubricDataset(source="mem", sha256="0" * 64, examples=tuple(examples))


def test_score_configuration_breakdowns_missing_and_coverage() -> None:
    disclaimer = {"type": "disclaimer"}
    rows = []
    for prompt_id, theme in (("a", "hedging"), ("b", "hedging"), ("c", "emergency")):
        rows.append(
            RubricExample.model_validate(
                {
                    "prompt_id": prompt_id,
                    "prompt": [{"role": "user", "content": "q"}],
                    "rubrics": [
                        {"criterion": "d", "points": 4, "tags": ["axis:x"], "check": disclaimer},
                        {"criterion": "u", "points": 4},
                    ],
                    "example_tags": [f"theme:{theme}"],
                }
            )
        )
    responses = {"a": "RESEARCH USE ONLY.", "b": "plain answer"}
    result = score_configuration("cfg", _dataset(*rows), responses, bootstrap_samples=50)
    assert result.missing == ("c",)
    assert [r.score for r in result.examples] == [1.0, 0.0]
    assert result.overall.score == 0.5
    assert result.themes["hedging"].n == 2
    assert "emergency" not in result.themes
    assert result.axes["x"].score == 0.5
    assert result.coverage == 0.5
    summary = result.to_dict()
    assert summary["criteria"] == {"total": 4, "graded": 2, "met": 1, "not_met": 1, "ungraded": 2}
    assert summary["examples_missing_response"] == ["c"]


def test_precomputed_grades_replace_the_rule_grader() -> None:
    example = _example(points=(3,))
    grades = {"p": [_grade(3, MET)]}
    result = score_configuration("cfg", _dataset(example), {"p": "x"}, graded=grades)
    assert result.overall.score == 1.0


def test_bootstrap_is_seeded_and_bounded() -> None:
    values = [0.1, 0.9, 0.4, 0.7, 0.0, 1.0, 0.3]
    first = bootstrap_interval(values, samples=500, seed=7)
    assert first == bootstrap_interval(values, samples=500, seed=7)
    assert first != bootstrap_interval(values, samples=500, seed=8)
    low, high, std = first
    assert 0.0 <= low <= high <= 1.0
    assert std > 0
    assert bootstrap_interval([0.5, 0.5], samples=10) == (0.5, 0.5, 0.0)


def test_bootstrap_clips_resampled_means() -> None:
    low, high, _std = bootstrap_interval([-2.0, -1.0, 0.5], samples=300, seed=1)
    assert low == 0.0
    assert high <= 0.5


def test_aggregate_without_bootstrap_and_empty() -> None:
    agg = aggregate([0.2, 0.4], bootstrap_samples=0)
    assert (agg.ci_low, agg.ci_high, agg.bootstrap_std) == (None, None, None)
    assert aggregate([]).to_dict()["score"] is None


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"values": []}, "at least one value"),
        ({"samples": 0}, "samples must be within"),
        ({"seed": -1}, "non-negative"),
        ({"confidence": 1.0}, "confidence"),
    ],
)
def test_bootstrap_rejects_invalid_settings(kwargs: dict[str, Any], message: str) -> None:
    arguments: dict[str, Any] = {"values": [0.5], **kwargs}
    values = arguments.pop("values")
    with pytest.raises(ValueError, match=message):
        bootstrap_interval(values, **arguments)
