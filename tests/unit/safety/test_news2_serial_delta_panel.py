"""Unit tests for News2SerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.news2_serial_delta_panel import (
    News2SerialDeltaFactors,
    News2SerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = News2SerialDeltaPanel().check(News2SerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = News2SerialDeltaPanel().check(
        News2SerialDeltaFactors(prior_news2_elevated=1, current_news2_rise=1)
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = News2SerialDeltaPanel().check(
        News2SerialDeltaFactors(
            prior_news2_elevated=1,
            current_news2_rise=1,
            multi_parameter_rise=1,
            oxygen_escalation=1,
            consciousness_worsening=1,
            ward_escalation_flag=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        News2SerialDeltaPanel().check(News2SerialDeltaFactors(prior_news2_elevated=4))
