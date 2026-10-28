"""Unit tests for OttawaAnkleSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.ottawa_ankle_serial_delta_panel import (
    OttawaAnkleSerialDeltaFactors,
    OttawaAnkleSerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = OttawaAnkleSerialDeltaPanel().check(OttawaAnkleSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = OttawaAnkleSerialDeltaPanel().check(
        OttawaAnkleSerialDeltaFactors(
            prior_ottawa_positive=1,
            malleolar_pain_new=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = OttawaAnkleSerialDeltaPanel().check(
        OttawaAnkleSerialDeltaFactors(
            prior_ottawa_positive=1,
            malleolar_pain_new=1,
            navicular_pain_new=1,
            base_fifth_pain_new=1,
            inability_bear_weight_new=1,
            swelling_worsened=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Out-of-range factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        OttawaAnkleSerialDeltaPanel().check(OttawaAnkleSerialDeltaFactors(prior_ottawa_positive=2))
