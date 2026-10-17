"""Tests for CamIcuDeliriumScorer."""

from __future__ import annotations

import pytest

from medagent.safety.cam_icu_delirium_scorer import (
    CamIcuDeliriumFactors,
    CamIcuDeliriumScorer,
)


def test_low() -> None:
    """Low band."""

    findings = CamIcuDeliriumScorer().check(CamIcuDeliriumFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = CamIcuDeliriumScorer().check(
        CamIcuDeliriumFactors(
            acute_change=1,
            inattention=1,
            disorganized_thinking=1,
            altered_consciousness=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid() -> None:
    """Invalid factor raises."""

    with pytest.raises(ValueError):
        CamIcuDeliriumScorer().check(CamIcuDeliriumFactors(acute_change=2))
