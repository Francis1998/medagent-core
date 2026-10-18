"""Tests for RassSedationScorer."""

from __future__ import annotations

import pytest

from medagent.safety.rass_sedation_scorer import (
    RassSedationFactors,
    RassSedationScorer,
)


def test_low() -> None:
    """Low band."""

    findings = RassSedationScorer().check(RassSedationFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = RassSedationScorer().check(
        RassSedationFactors(
            restless_agitated=1,
            combative=1,
            drowsy=1,
            light_sedation=1,
            moderate_sedation=1,
            deep_sedation=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid() -> None:
    """Invalid factor raises."""

    with pytest.raises(ValueError):
        RassSedationScorer().check(RassSedationFactors(restless_agitated=2))
