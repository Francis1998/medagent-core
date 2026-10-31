"""Tests for GlasgowBlatchfordSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.glasgow_blatchford_serial_delta_panel import (
    GlasgowBlatchfordSerialDeltaFactors,
    GlasgowBlatchfordSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = GlasgowBlatchfordSerialDeltaPanel().check(GlasgowBlatchfordSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = dict.fromkeys(
        [
            "prior_gbs_elevated",
            "bun_rise",
            "hb_drop",
            "sbp_drop",
            "melena_new",
            "syncope_new",
        ],
        1,
    )
    panel = GlasgowBlatchfordSerialDeltaPanel()
    findings = panel.check(GlasgowBlatchfordSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        GlasgowBlatchfordSerialDeltaPanel().check(
            GlasgowBlatchfordSerialDeltaFactors(prior_gbs_elevated=2)
        )
