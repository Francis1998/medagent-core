"""Tests for amiodarone + thyroid lab trend monitoring bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import AmiodaroneThyroidBridge as ExportedBridge
from medagent.safety.amio_warfarin_checker import AmioWarfarinChecker
from medagent.safety.amiodarone_digoxin_checker import AmiodaroneDigoxinChecker
from medagent.safety.amiodarone_thyroid_bridge import AmiodaroneThyroidBridge


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_rising_tsh_on_amiodarone() -> None:
    labs = [
        {"name": "TSH", "value": 2.0, "unit": "mIU/L", "drawn_at": "2026-01-01"},
        {"name": "TSH", "value": 8.5, "unit": "mIU/L", "drawn_at": "2026-04-01"},
    ]
    findings = AmiodaroneThyroidBridge().check(
        medications=_meds("Amiodarone 200 mg"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "rising_tsh_on_amiodarone")
    assert hit.severity in {Severity.HIGH, Severity.CRITICAL}
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale
    assert hit.tsh_values == [2.0, 8.5]


def test_falling_tsh_on_amiodarone() -> None:
    labs = [
        {"name": "tsh", "value": 3.0, "drawn_at": "a"},
        {"name": "tsh", "value": 0.1, "drawn_at": "b"},
    ]
    findings = AmiodaroneThyroidBridge().check(
        medications=_meds("Amiodarone"),
        labs=labs,
    )
    assert any(f.finding_kind == "falling_tsh_on_amiodarone" for f in findings)


def test_abnormal_ft4_trend_on_amiodarone() -> None:
    labs = [
        {"name": "free T4", "value": 1.2, "drawn_at": "t0"},
        {"name": "FT4", "value": 2.8, "drawn_at": "t1"},
    ]
    findings = AmiodaroneThyroidBridge().check(
        medications=_meds("Amiodarone"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "abnormal_ft4_trend_on_amiodarone")
    assert hit.ft4_values == [1.2, 2.8]
    assert hit.severity in {Severity.HIGH, Severity.CRITICAL}


def test_thyroid_monitoring_advisory() -> None:
    labs = [
        {"name": "TSH", "value": 0.2, "drawn_at": "1"},
        {"name": "TSH", "value": 12.0, "drawn_at": "2"},
        {"name": "FT4", "value": 0.5, "drawn_at": "2"},
    ]
    findings = AmiodaroneThyroidBridge().check(
        medications=_meds("Amiodarone"),
        labs=labs,
    )
    assert any(f.finding_kind == "amiodarone_thyroid_monitoring_advisory" for f in findings)


def test_no_amiodarone_no_findings() -> None:
    labs = [
        {"name": "TSH", "value": 1.0, "drawn_at": "1"},
        {"name": "TSH", "value": 10.0, "drawn_at": "2"},
    ]
    assert AmiodaroneThyroidBridge().check(medications=_meds("Warfarin"), labs=labs) == []


def test_amiodarone_without_abnormal_trend() -> None:
    labs = [
        {"name": "TSH", "value": 2.0, "drawn_at": "1"},
        {"name": "TSH", "value": 2.2, "drawn_at": "2"},
        {"name": "FT4", "value": 1.1, "drawn_at": "1"},
        {"name": "FT4", "value": 1.15, "drawn_at": "2"},
    ]
    findings = AmiodaroneThyroidBridge().check(
        medications=_meds("Amiodarone"),
        labs=labs,
    )
    assert findings == []


def test_distinct_from_amio_digoxin_and_amio_warfarin() -> None:
    assert AmiodaroneThyroidBridge is not AmiodaroneDigoxinChecker
    assert AmiodaroneThyroidBridge is not AmioWarfarinChecker
    meds = _meds("Amiodarone", "Digoxin", "Warfarin")
    labs = [
        {"name": "TSH", "value": 1.5, "drawn_at": "a"},
        {"name": "TSH", "value": 9.0, "drawn_at": "b"},
    ]
    thyroid = AmiodaroneThyroidBridge().check(medications=meds, labs=labs)
    assert thyroid
    assert AmiodaroneDigoxinChecker().check(meds)
    assert AmioWarfarinChecker().check(meds)


def test_whole_token_matching() -> None:
    findings = AmiodaroneThyroidBridge().check(
        medications=_meds("Pseudoamiodarone"),
        labs=[
            {"name": "TSH", "value": 1.0, "drawn_at": "1"},
            {"name": "TSH", "value": 10.0, "drawn_at": "2"},
        ],
    )
    assert findings == []


def test_never_modifies_medications() -> None:
    meds = _meds("Amiodarone")
    snapshot = [(m.name, m.model_dump()) for m in meds]
    labs = [
        {"name": "TSH", "value": 2.0, "drawn_at": "d1"},
        {"name": "TSH", "value": 11.0, "drawn_at": "d2"},
    ]
    findings = AmiodaroneThyroidBridge().check(medications=meds, labs=labs)
    assert findings
    assert [(m.name, m.model_dump()) for m in meds] == snapshot
    assert all("RESEARCH USE ONLY" in f.rationale for f in findings)


def test_exported() -> None:
    findings = ExportedBridge().check(
        medications=_meds("Amiodarone"),
        labs=[
            {"name": "free t4", "value": 1.0, "drawn_at": "d1"},
            {"name": "free t4", "value": 0.4, "drawn_at": "d2"},
        ],
    )
    assert findings
    assert all("Never modifies medications" in f.rationale for f in findings)
