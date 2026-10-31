"""Tests for OttawaSahSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.ottawa_sah_serial_delta_panel import (
    OttawaSahSerialDeltaFactors,
    OttawaSahSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = OttawaSahSerialDeltaPanel().check(OttawaSahSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = dict.fromkeys(
        [
            "prior_ottawa_sah_positive",
            "new_thunderclap",
            "neck_stiffness_new",
            "loc_witnessed_new",
            "exertion_onset_new",
            "limited_flexion_new",
        ],
        1,
    )
    findings = OttawaSahSerialDeltaPanel().check(OttawaSahSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        OttawaSahSerialDeltaPanel().check(OttawaSahSerialDeltaFactors(prior_ottawa_sah_positive=2))
