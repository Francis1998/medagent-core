"""Tests for GraceSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.grace_serial_delta_panel import GraceSerialDeltaFactors, GraceSerialDeltaPanel


def test_low_band() -> None:
    """Low score band."""

    findings = GraceSerialDeltaPanel().check(GraceSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = dict.fromkeys(
        [
            "prior_grace_elevated",
            "age_factor_new",
            "heart_rate_worsened",
            "systolic_bp_dropped",
            "creatinine_rise",
            "killip_class_worsened",
        ],
        1,
    )
    findings = GraceSerialDeltaPanel().check(GraceSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        GraceSerialDeltaPanel().check(GraceSerialDeltaFactors(prior_grace_elevated=2))
