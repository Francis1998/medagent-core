"""Tests for Bayesian scoring functions."""

from __future__ import annotations

import pytest

from medagent.models import EvidenceItem, Hypothesis
from medagent.reasoning.bayesian import bayesian_score, calibrate_confidence, rank_hypotheses


def _make_evidence(direction: str, strength: float) -> EvidenceItem:
    """Convenience factory for test evidence items."""
    return EvidenceItem(direction=direction, statement="test statement", strength=strength)


class TestBayesianScore:
    """Tests for the bayesian_score function."""

    def test_output_in_unit_interval(self) -> None:
        """bayesian_score must always return a value in [0, 1]."""
        score = bayesian_score([], [])
        assert 0.0 <= score <= 1.0

    def test_strong_for_evidence_raises_score(self) -> None:
        """Strong FOR evidence must increase score above the prior."""
        prior = 0.3
        score = bayesian_score(
            [_make_evidence("FOR", 0.9), _make_evidence("FOR", 0.85)],
            [],
            prior=prior,
        )
        # Should be substantially higher than the prior
        assert score > prior

    def test_strong_against_evidence_lowers_score(self) -> None:
        """Strong AGAINST evidence must decrease score below the prior."""
        prior = 0.7
        score = bayesian_score(
            [],
            [_make_evidence("AGAINST", 0.9)],
            prior=prior,
        )
        assert score < prior

    def test_balanced_evidence_stays_near_prior(self) -> None:
        """Equal FOR and AGAINST evidence must keep the score close to the prior."""
        score = bayesian_score(
            [_make_evidence("FOR", 0.7)],
            [_make_evidence("AGAINST", 0.7)],
            prior=0.5,
        )
        assert abs(score - 0.5) < 0.15

    def test_invalid_prior_raises(self) -> None:
        """Prior of 0 or 1 must raise an AssertionError."""
        with pytest.raises(AssertionError):
            bayesian_score([], [], prior=0.0)
        with pytest.raises(AssertionError):
            bayesian_score([], [], prior=1.0)


class TestRankHypotheses:
    """Tests for rank_hypotheses ordering and rank assignment."""

    def test_ranked_by_descending_score(self) -> None:
        """Hypotheses must be ordered from highest to lowest Bayesian score."""
        hyps = [
            Hypothesis(
                label="H1",
                evidence_for=[_make_evidence("FOR", 0.3)],
                evidence_against=[_make_evidence("AGAINST", 0.9)],
            ),
            Hypothesis(
                label="H2",
                evidence_for=[_make_evidence("FOR", 0.9), _make_evidence("FOR", 0.85)],
                evidence_against=[],
            ),
        ]
        ranked = rank_hypotheses(hyps)
        assert ranked[0].label == "H2"
        assert ranked[0].rank == 1
        assert ranked[1].label == "H1"
        assert ranked[1].rank == 2

    def test_single_hypothesis_ranked_first(self) -> None:
        """A single hypothesis must have rank=1."""
        hyp = Hypothesis(label="only", evidence_for=[], evidence_against=[])
        ranked = rank_hypotheses([hyp])
        assert ranked[0].rank == 1

    def test_empty_list_returns_empty(self) -> None:
        """Empty input must produce empty output."""
        assert rank_hypotheses([]) == []


class TestCalibrateConfidence:
    """Tests for calibrate_confidence aggregation."""

    def test_high_consensus_gives_high_confidence(self) -> None:
        """Three similar high scores must produce higher confidence than a low prior."""
        confidence = calibrate_confidence([0.9, 0.88, 0.85])
        # Entropy penalty applies when scores are similar; 0.6 is the meaningful threshold
        assert confidence > 0.6

    def test_uniform_low_scores_give_low_confidence(self) -> None:
        """All equal low scores must produce low overall confidence."""
        confidence = calibrate_confidence([0.2, 0.2, 0.2])
        assert confidence < 0.3

    def test_empty_scores_return_zero(self) -> None:
        """Empty score list must return 0.0."""
        assert calibrate_confidence([]) == 0.0

    def test_result_in_unit_interval(self) -> None:
        """calibrate_confidence must always return a value in [0, 1]."""
        for scores in [
            [1.0, 0.9, 0.8],
            [0.1, 0.1],
            [0.5],
            [],
        ]:
            result = calibrate_confidence(scores)
            assert 0.0 <= result <= 1.0, f"Out of range for {scores}: {result}"
