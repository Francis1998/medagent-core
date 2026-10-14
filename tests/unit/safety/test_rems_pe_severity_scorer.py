"""Tests for RemsPeSeverityScorer."""

from __future__ import annotations

import pytest

from medagent.safety.rems_pe_severity_scorer import (
    RemsPeSeverityFactors,
    RemsPeSeverityScorer,
)


def test_low() -> None:
    """Low band."""

    findings = RemsPeSeverityScorer().check(RemsPeSeverityFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = RemsPeSeverityScorer().check(
        RemsPeSeverityFactors(
            rv_strain_ok=1,
            troponin_ok=1,
            bnp_ok=1,
            hypotension_ok=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid() -> None:
    """Invalid factor raises."""

    with pytest.raises(ValueError):
        RemsPeSeverityScorer().check(RemsPeSeverityFactors(rv_strain_ok=2))
