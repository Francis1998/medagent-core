"""Unit tests for QsofaSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.qsofa_serial_delta_panel import (
    QsofaSerialDeltaFactors,
    QsofaSerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = QsofaSerialDeltaPanel().check(QsofaSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = QsofaSerialDeltaPanel().check(
        QsofaSerialDeltaFactors(prior_qsofa_elevated=1, current_qsofa_rise=1)
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = QsofaSerialDeltaPanel().check(
        QsofaSerialDeltaFactors(
            prior_qsofa_elevated=1,
            current_qsofa_rise=1,
            rr_worsening=1,
            sbp_drop=1,
            ams_new=1,
            ward_escalation_flag=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        QsofaSerialDeltaPanel().check(QsofaSerialDeltaFactors(prior_qsofa_elevated=4))
