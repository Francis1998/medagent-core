"""Tests for KarnofskySerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.karnofsky_serial_delta_panel import (
    KarnofskySerialDeltaFactors,
    KarnofskySerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = KarnofskySerialDeltaPanel().check(KarnofskySerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = dict.fromkeys(
        [
            "prior_kps_drop",
            "ambulation_decline",
            "self_care_loss",
            "work_capacity_drop",
            "hospitalization_signal",
            "symptom_burden_rise",
        ],
        1,
    )
    panel = KarnofskySerialDeltaPanel()
    findings = panel.check(KarnofskySerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        KarnofskySerialDeltaPanel().check(KarnofskySerialDeltaFactors(prior_kps_drop=2))
