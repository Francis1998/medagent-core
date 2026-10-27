"""Unit tests for GcsSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.gcs_serial_delta_panel import (
    GcsSerialDeltaFactors,
    GcsSerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = GcsSerialDeltaPanel().check(GcsSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = GcsSerialDeltaPanel().check(
        GcsSerialDeltaFactors(
            prior_gcs_depressed=1,
            eye_down=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = GcsSerialDeltaPanel().check(
        GcsSerialDeltaFactors(
            prior_gcs_depressed=1,
            eye_down=1,
            verbal_down=1,
            motor_down=1,
            pupil_asymmetry_new=1,
            sedation_confound_new=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Out-of-range factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        GcsSerialDeltaPanel().check(GcsSerialDeltaFactors(prior_gcs_depressed=2))
