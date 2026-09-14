"""Tests for vancomycin + serial trough toxicity/underdosing bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import VancomycinTroughTrendBridge as ExportedBridge
from medagent.safety.gentamicin_vancomycin_checker import GentamicinVancomycinChecker
from medagent.safety.vancomycin_trough_trend_bridge import VancomycinTroughTrendBridge


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_supratherapeutic_trough() -> None:
    labs = [
        {"name": "vancomycin trough", "value": 18.0, "drawn_at": "2026-01-01"},
        {"name": "vancomycin trough", "value": 32.0, "drawn_at": "2026-01-03"},
    ]
    findings = VancomycinTroughTrendBridge().check(
        medications=_meds("Vancomycin IV"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "supratherapeutic_vancomycin_trough")
    assert hit.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale
    assert hit.trough_values == [18.0, 32.0]


def test_subtherapeutic_trough() -> None:
    labs = [
        {"name": "vanco trough", "value": 12.0, "drawn_at": "a"},
        {"name": "vanco trough", "value": 7.0, "drawn_at": "b"},
    ]
    findings = VancomycinTroughTrendBridge().check(
        medications=_meds("Vancocin"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "subtherapeutic_vancomycin_trough")
    assert hit.severity in {Severity.HIGH, Severity.MODERATE}
    assert hit.latest_trough == 7.0


def test_rising_trough() -> None:
    labs = [
        {"name": "vancomycin level", "value": 15.0, "drawn_at": "1"},
        {"name": "vancomycin level", "value": 24.0, "drawn_at": "2"},
    ]
    findings = VancomycinTroughTrendBridge().check(
        medications=_meds("Vancomycin"),
        labs=labs,
    )
    assert any(f.finding_kind == "rising_vancomycin_trough" for f in findings)
    assert any(f.finding_kind == "vancomycin_trough_monitoring_advisory" for f in findings)


def test_no_vancomycin_no_findings() -> None:
    labs = [
        {"name": "vancomycin trough", "value": 10.0, "drawn_at": "1"},
        {"name": "vancomycin trough", "value": 25.0, "drawn_at": "2"},
    ]
    assert VancomycinTroughTrendBridge().check(medications=_meds("Gentamicin"), labs=labs) == []


def test_vancomycin_therapeutic_band_no_findings() -> None:
    labs = [
        {"name": "vancomycin trough", "value": 12.0, "drawn_at": "1"},
        {"name": "vancomycin trough", "value": 15.0, "drawn_at": "2"},
    ]
    findings = VancomycinTroughTrendBridge().check(
        medications=_meds("Vancomycin"),
        labs=labs,
    )
    assert findings == []


def test_sorts_by_drawn_at() -> None:
    findings = VancomycinTroughTrendBridge().check(
        medications=_meds("Vancomycin"),
        labs=[
            {"name": "trough", "value": 28.0, "drawn_at": "2026-01-05"},
            {"name": "trough", "value": 14.0, "drawn_at": "2026-01-01"},
        ],
    )
    hit = next(f for f in findings if f.finding_kind == "rising_vancomycin_trough")
    assert hit.trough_values == [14.0, 28.0]


def test_distinct_from_gentamicin_vancomycin() -> None:
    assert VancomycinTroughTrendBridge is not GentamicinVancomycinChecker
    meds = _meds("Vancomycin", "Gentamicin")
    labs = [
        {"name": "vancomycin trough", "value": 15.0, "drawn_at": "a"},
        {"name": "vancomycin trough", "value": 26.0, "drawn_at": "b"},
    ]
    assert VancomycinTroughTrendBridge().check(medications=meds, labs=labs)
    assert GentamicinVancomycinChecker().check(meds)


def test_whole_token_matching() -> None:
    findings = VancomycinTroughTrendBridge().check(
        medications=_meds("Pseudovancomycin"),
        labs=[
            {"name": "vancomycin trough", "value": 10.0, "drawn_at": "1"},
            {"name": "vancomycin trough", "value": 30.0, "drawn_at": "2"},
        ],
    )
    assert findings == []


def test_never_modifies_medications() -> None:
    meds = _meds("Vancomycin", "Vancocin")
    snapshot = [(m.name, m.model_dump()) for m in meds]
    labs = [
        {"name": "vancomycin trough", "value": 8.0, "drawn_at": "d1"},
        {"name": "vancomycin trough", "value": 9.0, "drawn_at": "d2"},
    ]
    findings = VancomycinTroughTrendBridge().check(medications=meds, labs=labs)
    assert findings
    assert [(m.name, m.model_dump()) for m in meds] == snapshot


def test_exported() -> None:
    findings = ExportedBridge().check(
        medications=_meds("Vancomycin"),
        labs=[
            {"name": "vancomycin trough", "value": 22.0, "drawn_at": "d1"},
            {"name": "vancomycin trough", "value": 25.0, "drawn_at": "d2"},
        ],
    )
    assert findings
    assert all("Never modifies medications" in f.rationale for f in findings)
