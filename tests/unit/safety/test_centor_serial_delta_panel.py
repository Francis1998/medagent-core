"""Unit tests for CentorSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.centor_serial_delta_panel import (
    CentorSerialDeltaFactors,
    CentorSerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = CentorSerialDeltaPanel().check(CentorSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = CentorSerialDeltaPanel().check(
        CentorSerialDeltaFactors(
            prior_centor_elevated=1,
            new_fever=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = CentorSerialDeltaPanel().check(
        CentorSerialDeltaFactors(
            prior_centor_elevated=1,
            new_fever=1,
            new_tender_nodes=1,
            tonsil_exudate_new=1,
            cough_absent_new=1,
            age_band_up=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Out-of-range factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        CentorSerialDeltaPanel().check(CentorSerialDeltaFactors(prior_centor_elevated=2))
