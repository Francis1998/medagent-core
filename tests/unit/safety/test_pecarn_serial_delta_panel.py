"""Tests for PecarnSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.pecarn_serial_delta_panel import (
    PecarnSerialDeltaFactors,
    PecarnSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = PecarnSerialDeltaPanel().check(PecarnSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = dict.fromkeys(
        [
            "prior_pecarn_elevated",
            "gcs_drop",
            "altered_mental_new",
            "palpable_skull_fracture_new",
            "severe_mechanism_new",
            "acting_abnormal_new",
        ],
        1,
    )
    findings = PecarnSerialDeltaPanel().check(PecarnSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        PecarnSerialDeltaPanel().check(PecarnSerialDeltaFactors(prior_pecarn_elevated=2))
