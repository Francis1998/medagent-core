"""Tests for carbamazepine + serial serum level trend bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import CarbamazepineLevelTrendBridge as ExportedBridge
from medagent.safety.carbamazepine_level_trend_bridge import CarbamazepineLevelTrendBridge


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_rising_level() -> None:
    labs = [
        {"name": "serum carbamazepine", "value": 6.0, "drawn_at": "2026-01-01"},
        {"name": "serum carbamazepine", "value": 14.0, "drawn_at": "2026-01-15"},
    ]
    findings = CarbamazepineLevelTrendBridge().check(
        medications=_meds("Carbamazepine"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "rising_carbamazepine_level")
    assert hit.severity in {Severity.HIGH, Severity.CRITICAL}
    assert "RESEARCH USE ONLY" in hit.rationale


def test_supratherapeutic_level() -> None:
    labs = [
        {"name": "carbamazepine level", "value": 14.0, "drawn_at": "a"},
        {"name": "carbamazepine level", "value": 18.0, "drawn_at": "b"},
    ]
    findings = CarbamazepineLevelTrendBridge().check(
        medications=_meds("Tegretol"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "supratherapeutic_carbamazepine_level")
    assert hit.severity is Severity.CRITICAL


def test_no_meds() -> None:
    assert CarbamazepineLevelTrendBridge().check(medications=[], labs=[]) == []


def test_exported() -> None:
    assert ExportedBridge is CarbamazepineLevelTrendBridge
