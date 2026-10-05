"""Unit tests for NexusCspineScorer."""

from __future__ import annotations

import pytest

from medagent.safety.nexus_cspine_scorer import (
    NexusCspineFactors,
    NexusCspineScorer,
)


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = NexusCspineScorer().check(NexusCspineFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_high_band() -> None:
    """Many factors elevate band."""

    findings = NexusCspineScorer().check(
        NexusCspineFactors(
            midline_tenderness=1,
            altered_alertness=1,
            intoxication=1,
            focal_neuro_deficit=1,
            distracting_injury=1,
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        NexusCspineScorer().check(NexusCspineFactors(midline_tenderness=2))
