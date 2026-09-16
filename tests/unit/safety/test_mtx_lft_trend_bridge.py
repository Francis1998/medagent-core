"""Tests for methotrexate + serial ALT/AST LFT hepatotoxicity-trend bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import MtxLftTrendBridge as ExportedBridge
from medagent.safety.mtx_folate_checker import MtxFolateChecker
from medagent.safety.mtx_lft_trend_bridge import MtxLftTrendBridge
from medagent.safety.mtx_tmpsmx_checker import MtxTmpsmxChecker
from medagent.safety.statin_lft_trend_bridge import StatinLftTrendBridge


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_rising_alt_on_mtx() -> None:
    labs = [
        {"name": "ALT", "value": 42.0, "drawn_at": "2026-01-01"},
        {"name": "ALT", "value": 128.0, "drawn_at": "2026-01-15"},
    ]
    findings = MtxLftTrendBridge().check(
        medications=_meds("Methotrexate 15 mg"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "rising_alt_on_mtx")
    assert hit.severity in {Severity.HIGH, Severity.CRITICAL}
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale
    assert hit.alt_values == [42.0, 128.0]


def test_elevated_lft_on_mtx() -> None:
    labs = [
        {"name": "AST", "value": 90.0, "drawn_at": "a"},
        {"name": "AST", "value": 210.0, "drawn_at": "b"},
    ]
    findings = MtxLftTrendBridge().check(
        medications=_meds("Trexall"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "elevated_lft_on_mtx")
    assert hit.severity is Severity.CRITICAL
    assert hit.latest_lft == 210.0


def test_hepatotoxicity_advisory() -> None:
    labs = [
        {"name": "alanine aminotransferase", "value": 50.0, "drawn_at": "1"},
        {"name": "alanine aminotransferase", "value": 95.0, "drawn_at": "2"},
    ]
    findings = MtxLftTrendBridge().check(
        medications=_meds("Rheumatrex"),
        labs=labs,
    )
    assert any(f.finding_kind == "mtx_hepatotoxicity_advisory" for f in findings)
    assert any(f.finding_kind == "rising_alt_on_mtx" for f in findings)


def test_no_mtx_no_findings() -> None:
    labs = [
        {"name": "ALT", "value": 40.0, "drawn_at": "1"},
        {"name": "ALT", "value": 180.0, "drawn_at": "2"},
    ]
    assert MtxLftTrendBridge().check(medications=_meds("Metformin"), labs=labs) == []


def test_mtx_stable_lft_no_findings() -> None:
    labs = [
        {"name": "ALT", "value": 30.0, "drawn_at": "1"},
        {"name": "ALT", "value": 32.0, "drawn_at": "2"},
    ]
    findings = MtxLftTrendBridge().check(
        medications=_meds("Methotrexate"),
        labs=labs,
    )
    assert findings == []


def test_sorts_by_drawn_at() -> None:
    findings = MtxLftTrendBridge().check(
        medications=_meds("Otrexup"),
        labs=[
            {"name": "ALT", "value": 150.0, "drawn_at": "2026-01-05"},
            {"name": "ALT", "value": 45.0, "drawn_at": "2026-01-01"},
        ],
    )
    hit = next(f for f in findings if f.finding_kind == "rising_alt_on_mtx")
    assert hit.alt_values == [45.0, 150.0]


def test_distinct_from_folate_tmpsmx_statin() -> None:
    assert MtxLftTrendBridge is not MtxFolateChecker
    assert MtxLftTrendBridge is not MtxTmpsmxChecker
    assert MtxLftTrendBridge is not StatinLftTrendBridge
    meds = _meds("Methotrexate")
    labs = [
        {"name": "ALT", "value": 40.0, "drawn_at": "a"},
        {"name": "ALT", "value": 120.0, "drawn_at": "b"},
    ]
    assert MtxLftTrendBridge().check(medications=meds, labs=labs)
    assert MtxFolateChecker().check(meds)


def test_whole_token_matching() -> None:
    findings = MtxLftTrendBridge().check(
        medications=_meds("Pseudomethotrexate"),
        labs=[
            {"name": "ALT", "value": 40.0, "drawn_at": "1"},
            {"name": "ALT", "value": 200.0, "drawn_at": "2"},
        ],
    )
    assert findings == []


def test_never_modifies_medications() -> None:
    meds = _meds("Methotrexate", "Rasuvo")
    snapshot = [(m.name, m.model_dump()) for m in meds]
    labs = [
        {"name": "ALT", "value": 55.0, "drawn_at": "d1"},
        {"name": "ALT", "value": 110.0, "drawn_at": "d2"},
    ]
    findings = MtxLftTrendBridge().check(medications=meds, labs=labs)
    assert findings
    assert [(m.name, m.model_dump()) for m in meds] == snapshot


def test_exported() -> None:
    findings = ExportedBridge().check(
        medications=_meds("Xatmep"),
        labs=[
            {"name": "AST", "value": 70.0, "drawn_at": "d1"},
            {"name": "AST", "value": 160.0, "drawn_at": "d2"},
        ],
    )
    assert findings
    assert all("Never modifies medications" in f.rationale for f in findings)
