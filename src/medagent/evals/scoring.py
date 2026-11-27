"""HealthBench scoring with ungraded criteria, axis/theme breakdowns and a seeded bootstrap CI.

Per example, as in HealthBench's ``calculate_score``::

    score = Σ points of met criteria / Σ points of positive criteria

restricted to *graded* criteria: an ``ungraded`` criterion is excluded from both
the numerator and the denominator, and counted in the result. An example whose
graded criteria carry no positive points has no score (``None``); it is left out
of the aggregate and counted as unscorable. Example scores are not clipped (an
answer that meets negative criteria can score below 0). The aggregate is the
mean of example scores clipped to [0, 1]; its uncertainty is a percentile
bootstrap confidence interval plus HealthBench's ``bootstrap_std``, both over
clipped means of resampled example scores drawn from a seeded generator.

Axis scores apply the same formula to the criteria tagged ``axis:<name>``;
theme scores average the example scores of examples tagged ``theme:<name>``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from medagent.evals.dataset import RubricDataset, RubricExample
from medagent.evals.grader import MET, NOT_MET, UNGRADED, CriterionGrade, grade_response

DEFAULT_BOOTSTRAP_SAMPLES = 1000
DEFAULT_SEED = 0
DEFAULT_CONFIDENCE = 0.95
MAX_BOOTSTRAP_SAMPLES = 100_000
_BOOTSTRAP_CHUNK = 200


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


@dataclass(frozen=True)
class Aggregate:
    """Clipped mean of example-level scores with its bootstrap uncertainty.

    Attributes:
        score: Mean clipped to [0, 1]; ``None`` when no example is scorable.
        mean: Unclipped mean (can be negative).
        ci_low: Lower bound of the percentile bootstrap CI.
        ci_high: Upper bound of the percentile bootstrap CI.
        bootstrap_std: Standard deviation of the clipped bootstrap means.
        n: Number of example scores aggregated.
    """

    score: float | None
    mean: float | None
    ci_low: float | None
    ci_high: float | None
    bootstrap_std: float | None
    n: int

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable form (rounded to 4 decimals)."""
        return {
            "score": _round(self.score),
            "mean_unclipped": _round(self.mean),
            "ci_low": _round(self.ci_low),
            "ci_high": _round(self.ci_high),
            "bootstrap_std": _round(self.bootstrap_std),
            "n": self.n,
        }


def bootstrap_interval(
    values: Sequence[float],
    *,
    samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    seed: int = DEFAULT_SEED,
    confidence: float = DEFAULT_CONFIDENCE,
) -> tuple[float, float, float]:
    """Percentile bootstrap CI and standard deviation of the clipped mean.

    Args:
        values: Example-level scores (at least one).
        samples: Number of resamples (with replacement, same size as ``values``).
        seed: Seed for ``numpy.random.default_rng``; equal inputs give equal output.
        confidence: Two-sided confidence level in (0, 1).

    Returns:
        ``(ci_low, ci_high, bootstrap_std)``.

    Raises:
        ValueError: Empty ``values``, ``samples`` outside 1-100,000, a negative
            ``seed`` or ``confidence`` outside (0, 1).
    """
    if not values:
        raise ValueError("bootstrap needs at least one value")
    if not 1 <= samples <= MAX_BOOTSTRAP_SAMPLES:
        raise ValueError(f"samples must be within 1-{MAX_BOOTSTRAP_SAMPLES}")
    if seed < 0:
        raise ValueError("seed must be a non-negative integer")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be within (0, 1)")
    data = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means: list[np.ndarray[Any, np.dtype[np.float64]]] = []
    for start in range(0, samples, _BOOTSTRAP_CHUNK):
        size = min(_BOOTSTRAP_CHUNK, samples - start)
        indices = rng.integers(0, len(data), size=(size, len(data)))
        means.append(np.clip(data[indices].mean(axis=1), 0.0, 1.0))
    clipped = np.concatenate(means)
    tail = (1.0 - confidence) / 2.0
    low, high = np.quantile(clipped, [tail, 1.0 - tail])
    return float(low), float(high), float(clipped.std())


def aggregate(
    values: Sequence[float],
    *,
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    seed: int = DEFAULT_SEED,
    confidence: float = DEFAULT_CONFIDENCE,
) -> Aggregate:
    """Aggregate example-level scores; ``bootstrap_samples=0`` skips the CI."""
    if not values:
        return Aggregate(None, None, None, None, None, 0)
    mean = float(np.mean(np.asarray(values, dtype=float)))
    ci_low = ci_high = std = None
    if bootstrap_samples:
        ci_low, ci_high, std = bootstrap_interval(
            values, samples=bootstrap_samples, seed=seed, confidence=confidence
        )
    return Aggregate(
        score=min(1.0, max(0.0, mean)),
        mean=mean,
        ci_low=ci_low,
        ci_high=ci_high,
        bootstrap_std=std,
        n=len(values),
    )


def _ratio(grades: Sequence[CriterionGrade]) -> tuple[float | None, float, float]:
    """Return (score, achieved points, graded positive points) over graded criteria."""
    graded = [g for g in grades if g.verdict != UNGRADED]
    possible = sum(g.points for g in graded if g.points > 0)
    achieved = sum(g.points for g in graded if g.verdict == MET)
    return (achieved / possible if possible > 0 else None), achieved, possible


@dataclass(frozen=True)
class ExampleResult:
    """Grades and scores for one example under one configuration."""

    prompt_id: str
    score: float | None
    achieved_points: float
    graded_positive_points: float
    total_positive_points: float
    axis_scores: Mapping[str, float]
    themes: tuple[str, ...]
    grades: tuple[CriterionGrade, ...]
    response_chars: int

    def count(self, verdict: str) -> int:
        """Number of criteria with ``verdict``."""
        return sum(1 for grade in self.grades if grade.verdict == verdict)

    def points_lost(self) -> list[CriterionGrade]:
        """Graded criteria that cost points: positive ones not met, negative ones met."""
        return [
            g
            for g in self.grades
            if (g.points > 0 and g.verdict == NOT_MET) or (g.points < 0 and g.verdict == MET)
        ]

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable form."""
        return {
            "prompt_id": self.prompt_id,
            "score": _round(self.score),
            "achieved_points": self.achieved_points,
            "graded_positive_points": self.graded_positive_points,
            "total_positive_points": self.total_positive_points,
            "axis_scores": {axis: _round(v) for axis, v in sorted(self.axis_scores.items())},
            "themes": list(self.themes),
            "criteria": {
                "met": self.count(MET),
                "not_met": self.count(NOT_MET),
                "ungraded": self.count(UNGRADED),
            },
            "response_chars": self.response_chars,
            "grades": [grade.to_dict() for grade in self.grades],
        }


def score_example(
    example: RubricExample, grades: Sequence[CriterionGrade], response_chars: int = 0
) -> ExampleResult:
    """Score one example from its criterion grades (see the module docstring)."""
    score, achieved, possible = _ratio(grades)
    axis_scores: dict[str, float] = {}
    for axis in sorted({axis for grade in grades for axis in grade.axes}):
        axis_score, _, _ = _ratio([g for g in grades if axis in g.axes])
        if axis_score is not None:
            axis_scores[axis] = axis_score
    return ExampleResult(
        prompt_id=example.prompt_id,
        score=score,
        achieved_points=achieved,
        graded_positive_points=possible,
        total_positive_points=sum(item.points for item in example.rubrics if item.points > 0),
        axis_scores=axis_scores,
        themes=example.themes,
        grades=tuple(grades),
        response_chars=response_chars,
    )


@dataclass(frozen=True)
class ConfigResult:
    """Every example's grades and the aggregate scores for one configuration."""

    label: str
    source: str
    n_examples: int
    examples: tuple[ExampleResult, ...]
    missing: tuple[str, ...]
    overall: Aggregate
    axes: Mapping[str, Aggregate] = field(default_factory=dict)
    themes: Mapping[str, Aggregate] = field(default_factory=dict)

    @property
    def unscorable(self) -> tuple[str, ...]:
        """Prompt ids whose graded criteria carry no positive points."""
        return tuple(r.prompt_id for r in self.examples if r.score is None)

    def count(self, verdict: str) -> int:
        """Number of criteria with ``verdict`` across all graded examples."""
        return sum(result.count(verdict) for result in self.examples)

    @property
    def coverage(self) -> float | None:
        """Share of positive points that were graded (1.0 = every positive criterion graded)."""
        total = sum(r.total_positive_points for r in self.examples)
        graded = sum(r.graded_positive_points for r in self.examples)
        return graded / total if total > 0 else None

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable form."""
        graded = self.count(MET) + self.count(NOT_MET)
        return {
            "label": self.label,
            "source": self.source,
            "overall": self.overall.to_dict(),
            "examples_total": self.n_examples,
            "examples_scored": self.overall.n,
            "examples_unscorable": list(self.unscorable),
            "examples_missing_response": list(self.missing),
            "criteria": {
                "total": graded + self.count(UNGRADED),
                "graded": graded,
                "met": self.count(MET),
                "not_met": self.count(NOT_MET),
                "ungraded": self.count(UNGRADED),
            },
            "graded_positive_points_coverage": _round(self.coverage),
            "axes": {name: agg.to_dict() for name, agg in sorted(self.axes.items())},
            "themes": {name: agg.to_dict() for name, agg in sorted(self.themes.items())},
            "examples": [result.to_dict() for result in self.examples],
        }


def score_configuration(
    label: str,
    dataset: RubricDataset,
    responses: Mapping[str, str],
    *,
    source: str = "",
    graded: Mapping[str, Sequence[CriterionGrade]] | None = None,
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    seed: int = DEFAULT_SEED,
    confidence: float = DEFAULT_CONFIDENCE,
) -> ConfigResult:
    """Grade and score one configuration's responses against ``dataset``.

    Args:
        label: Configuration name shown in reports (e.g. ``medagent-offline``).
        dataset: The rubric dataset.
        responses: ``prompt_id`` → response text; examples without a response
            are reported as missing and excluded.
        source: Where the responses came from (file path or generator name).
        graded: Pre-computed grades per ``prompt_id`` (for example after the
            optional LLM grader); otherwise the rule grader runs.
        bootstrap_samples: Bootstrap resamples per aggregate (0 = no CI).
        seed: Bootstrap seed; every aggregate uses the same seed.
        confidence: Confidence level of the bootstrap interval.

    Returns:
        The configuration's grades and aggregates.
    """
    results: list[ExampleResult] = []
    missing: list[str] = []
    for example in dataset.examples:
        response = responses.get(example.prompt_id)
        if response is None:
            missing.append(example.prompt_id)
            continue
        grades = (graded or {}).get(example.prompt_id)
        if grades is None:
            grades = grade_response(example, response)
        results.append(score_example(example, grades, len(response)))

    def agg(values: Sequence[float]) -> Aggregate:
        return aggregate(
            values, bootstrap_samples=bootstrap_samples, seed=seed, confidence=confidence
        )

    scored = [r for r in results if r.score is not None]
    axes = sorted({axis for r in results for axis in r.axis_scores})
    themes = sorted({theme for r in scored for theme in r.themes})
    return ConfigResult(
        label=label,
        source=source,
        n_examples=len(dataset.examples),
        examples=tuple(results),
        missing=tuple(missing),
        overall=agg([r.score for r in scored if r.score is not None]),
        axes={a: agg([r.axis_scores[a] for r in results if a in r.axis_scores]) for a in axes},
        themes={
            t: agg([r.score for r in scored if t in r.themes and r.score is not None])
            for t in themes
        },
    )
