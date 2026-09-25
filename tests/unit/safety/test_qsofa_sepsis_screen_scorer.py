"""Unit tests for QSofaSepsisScreenScorer."""

from __future__ import annotations

import pytest

from medagent.safety.qsofa_sepsis_screen_scorer import (
    QSofaSepsisScreenFactors,
    QSofaSepsisScreenScorer,
)


def test_default_band() -> None:
    """Default factors yield low advisory band."""

    findings = QSofaSepsisScreenScorer().check(QSofaSepsisScreenFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale.startswith("RESEARCH USE ONLY")


def test_high_band() -> None:
    """Two or more factors yield high band."""

    findings = QSofaSepsisScreenScorer().check(
        QSofaSepsisScreenFactors(
            respiratory_rate_ge_22=1,
            altered_mentation=1,
            systolic_bp_le_100=0,
        )
    )
    assert findings[0].band == "high"
    assert findings[0].score == 2


def test_invalid_factor_raises() -> None:
    """Non-binary factor raises ValueError."""

    with pytest.raises(ValueError, match="altered_mentation"):
        QSofaSepsisScreenScorer().check(QSofaSepsisScreenFactors(altered_mentation=2))
