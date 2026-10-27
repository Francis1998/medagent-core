"""Unit tests for AlvaradoSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.alvarado_serial_delta_panel import (
    AlvaradoSerialDeltaFactors,
    AlvaradoSerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = AlvaradoSerialDeltaPanel().check(AlvaradoSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = AlvaradoSerialDeltaPanel().check(
        AlvaradoSerialDeltaFactors(
            prior_alvarado_elevated=1,
            migration_pain_new=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = AlvaradoSerialDeltaPanel().check(
        AlvaradoSerialDeltaFactors(
            prior_alvarado_elevated=1,
            migration_pain_new=1,
            anorexia_new=1,
            nausea_vomit_new=1,
            rlq_tenderness_up=1,
            leukocytosis_up=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Out-of-range factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        AlvaradoSerialDeltaPanel().check(AlvaradoSerialDeltaFactors(prior_alvarado_elevated=2))
