"""Bayesian confidence scorer for clinical hypotheses.

Implements a simplified Bayesian update rule:
    posterior ∝ prior × P(evidence | hypothesis)

Evidence items update the running likelihood in log-space to avoid
numerical underflow. The final score is mapped to [0, 1] via a sigmoid.
"""

from __future__ import annotations

import math

from medagent.models import EvidenceItem, Hypothesis

# Evidence strength is clamped to this range before its log-odds weight is taken.
# 0.5 is neutral (the default strength), so an item's weight is never negative and
# it can only move its hypothesis in its labelled direction.
_NEUTRAL_STRENGTH = 0.5
_MAX_STRENGTH = 0.95


def bayesian_score(
    evidence_for: list[EvidenceItem],
    evidence_against: list[EvidenceItem],
    prior: float = 0.3,
) -> float:
    """Compute a Bayesian-inspired confidence score for a hypothesis.

    Uses a log-odds update rule:
        log_odds_posterior = log_odds_prior + Σ w(strength_i) for FOR
                                            - Σ w(strength_i) for AGAINST
        w(s) = log(s / (1 - s)), with s clamped to [0.5, 0.95]

    ``w`` is never negative, so supporting evidence can only raise the score and
    contradicting evidence can only lower it. A strength at or below the neutral
    0.5 adds no weight; the upper clamp avoids log(0).

    Args:
        evidence_for: Evidence items supporting the hypothesis.
        evidence_against: Evidence items refuting the hypothesis.
        prior: Prior probability of the hypothesis (default 0.3 for a
            differential diagnosis context with ~3 plausible hypotheses).

    Returns:
        Posterior probability in [0, 1].
    """
    assert 0.0 < prior < 1.0, "Prior must be in open interval (0, 1)"

    log_odds = math.log(prior / (1.0 - prior))

    for item in evidence_for:
        log_odds += _evidence_weight(item.strength)

    for item in evidence_against:
        # Against evidence subtracts likelihood
        log_odds -= _evidence_weight(item.strength)

    return _sigmoid(log_odds)


def _evidence_weight(strength: float) -> float:
    """Return the non-negative log-odds weight of one item in its own direction."""
    clamped = _clamp(strength, _NEUTRAL_STRENGTH, _MAX_STRENGTH)
    return math.log(clamped / (1.0 - clamped))


def _sigmoid(x: float) -> float:
    """Map log-odds back to [0, 1] probability via the sigmoid function."""
    return 1.0 / (1.0 + math.exp(-x))


def _clamp(value: float, lo: float, hi: float) -> float:
    """Clamp a float to the closed interval [lo, hi]."""
    return max(lo, min(hi, value))


def rank_hypotheses(hypotheses: list[Hypothesis]) -> list[Hypothesis]:
    """Recompute and sort hypotheses by Bayesian score, updating ranks.

    Args:
        hypotheses: Unranked hypothesis list.

    Returns:
        New list of Hypothesis objects with updated rank fields,
        sorted descending by bayesian_score.
    """
    scored = []
    for hyp in hypotheses:
        score = bayesian_score(hyp.evidence_for, hyp.evidence_against)
        scored.append((score, hyp))

    scored.sort(key=lambda t: t[0], reverse=True)

    return [
        hyp.model_copy(update={"bayesian_score": round(score, 4), "rank": rank + 1})
        for rank, (score, hyp) in enumerate(scored)
    ]


def calibrate_confidence(raw_scores: list[float]) -> float:
    """Compute overall confidence from a list of hypothesis scores.

    Uses Platt scaling approximation:
        confidence = mean(top_k) × (1 - entropy_penalty)

    The entropy penalty discounts situations where the top hypotheses
    are all nearly equally likely (high uncertainty).

    Args:
        raw_scores: Bayesian scores for each hypothesis, already sorted desc.

    Returns:
        Overall confidence in [0, 1].
    """
    if not raw_scores:
        return 0.0

    top_k = raw_scores[:3]
    mean_score = sum(top_k) / len(top_k)

    # Entropy penalty: high when all scores are equal
    if len(top_k) > 1:
        normalised = [s / (sum(top_k) + 1e-9) for s in top_k]
        entropy = -sum(p * math.log(p + 1e-9) for p in normalised)
        max_entropy = math.log(len(top_k))
        penalty = entropy / (max_entropy + 1e-9)
    else:
        penalty = 0.0

    return round(max(0.0, min(1.0, mean_score * (1.0 - 0.3 * penalty))), 4)
