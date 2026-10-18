"""Tests for BarthelAdlScorer."""

from __future__ import annotations

import pytest

from medagent.safety.barthel_adl_scorer import (
    BarthelAdlFactors,
    BarthelAdlScorer,
)


def test_low() -> None:
    """Low band."""

    findings = BarthelAdlScorer().check(BarthelAdlFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = BarthelAdlScorer().check(
        BarthelAdlFactors(
            feeding_dependent=1,
            bathing_dependent=1,
            dressing_dependent=1,
            toileting_dependent=1,
            transfer_dependent=1,
            mobility_dependent=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid() -> None:
    """Invalid factor raises."""

    with pytest.raises(ValueError):
        BarthelAdlScorer().check(BarthelAdlFactors(feeding_dependent=2))
