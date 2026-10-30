"""Tests for CanadianCtHeadSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.canadian_ct_head_serial_delta_panel import (
    CanadianCtHeadSerialDeltaFactors,
    CanadianCtHeadSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = CanadianCtHeadSerialDeltaPanel().check(CanadianCtHeadSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = dict.fromkeys(
        [
            "prior_rule_positive",
            "gcs_drop",
            "vomiting_new",
            "amnesia_worsened",
            "dangerous_mechanism_new",
            "anticoag_started",
        ],
        1,
    )
    findings = CanadianCtHeadSerialDeltaPanel().check(CanadianCtHeadSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        CanadianCtHeadSerialDeltaPanel().check(
            CanadianCtHeadSerialDeltaFactors(prior_rule_positive=2)
        )
