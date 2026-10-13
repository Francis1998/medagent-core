"""Tests for MallampatiAirwayScorer."""

from __future__ import annotations

import pytest

from medagent.safety.mallampati_airway_scorer import MallampatiAirwayFactors, MallampatiAirwayScorer


def test_low() -> None:
    """Low band."""

    findings = MallampatiAirwayScorer().check(MallampatiAirwayFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = MallampatiAirwayScorer().check(
        MallampatiAirwayFactors(class_i_ok=1, class_ii_ok=1, class_iii_ok=1, class_iv_ok=1)
    )
    assert findings[0].band == "high"


def test_invalid() -> None:
    """Invalid factor raises."""

    with pytest.raises(ValueError):
        MallampatiAirwayScorer().check(MallampatiAirwayFactors(class_i_ok=2))
