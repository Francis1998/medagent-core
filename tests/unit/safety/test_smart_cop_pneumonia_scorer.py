"""Tests for SmartCopPneumoniaScorer."""

from __future__ import annotations

import pytest

from medagent.safety.smart_cop_pneumonia_scorer import (
    SmartCopPneumoniaFactors,
    SmartCopPneumoniaScorer,
)


def test_low() -> None:
    """Low band."""

    findings = SmartCopPneumoniaScorer().check(SmartCopPneumoniaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = SmartCopPneumoniaScorer().check(
        SmartCopPneumoniaFactors(
            sbp_ok=1,
            multilobar_ok=1,
            albumin_ok=1,
            rr_ok=1,
            tachycardia_ok=1,
            confusion_ok=1,
            oxygenation_ok=1,
            ph_ok=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid() -> None:
    """Invalid factor raises."""

    with pytest.raises(ValueError):
        SmartCopPneumoniaScorer().check(SmartCopPneumoniaFactors(sbp_ok=2))
