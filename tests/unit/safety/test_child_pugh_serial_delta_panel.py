"""Unit tests for ChildPughSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.child_pugh_serial_delta_panel import (
    ChildPughSerialDeltaFactors,
    ChildPughSerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = ChildPughSerialDeltaPanel().check(ChildPughSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = ChildPughSerialDeltaPanel().check(
        ChildPughSerialDeltaFactors(
            prior_child_pugh_elevated=1,
            bilirubin_up=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = ChildPughSerialDeltaPanel().check(
        ChildPughSerialDeltaFactors(
            prior_child_pugh_elevated=1,
            bilirubin_up=1,
            albumin_down=1,
            inr_up=1,
            ascites_new=1,
            encephalopathy_new=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Out-of-range factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        ChildPughSerialDeltaPanel().check(ChildPughSerialDeltaFactors(prior_child_pugh_elevated=2))
