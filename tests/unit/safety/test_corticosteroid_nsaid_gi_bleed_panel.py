"""Tests for corticosteroid + NSAID GI-bleed panel."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import CorticosteroidNsaidGiBleedPanel as ExportedPanel
from medagent.safety.corticosteroid_nsaid_gi_bleed_panel import (
    CorticosteroidNsaidGiBleedPanel,
)
from medagent.safety.fluoroquinolone_corticosteroid_checker import (
    FluoroquinoloneCorticosteroidChecker,
)
from medagent.safety.nsaid_ssri_checker import NsaidSsriBleedChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_steroid_nsaid_gi_bleed() -> None:
    findings = CorticosteroidNsaidGiBleedPanel().check(
        medications=_meds("Prednisone", "Ibuprofen"),
    )
    hit = next(f for f in findings if f.finding_kind == "corticosteroid_nsaid_gi_bleed")
    assert hit.severity is Severity.HIGH
    assert hit.corticosteroids == ["prednisone"]
    assert hit.nsaids == ["ibuprofen"]
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale
    # Distinct: steroid+NSAID alone should not trip FQ+steroid or NSAID+SSRI
    assert FluoroquinoloneCorticosteroidChecker().check(_meds("Prednisone", "Ibuprofen")) == []
    assert NsaidSsriBleedChecker().check(_meds("Prednisone", "Ibuprofen")) == []


def test_multi_nsaid_on_corticosteroid() -> None:
    findings = CorticosteroidNsaidGiBleedPanel().check(
        medications=_meds("Dexamethasone", "Naproxen", "Meloxicam"),
    )
    multi = next(f for f in findings if f.finding_kind == "multi_nsaid_on_corticosteroid")
    assert multi.severity is Severity.CRITICAL
    assert set(multi.nsaids) == {"naproxen", "meloxicam"}


def test_multi_steroid_nsaid_stack() -> None:
    findings = CorticosteroidNsaidGiBleedPanel().check(
        medications=_meds("Prednisone", "Methylprednisolone", "Ketorolac"),
    )
    stack = next(f for f in findings if f.finding_kind == "multi_steroid_nsaid_stack")
    assert stack.severity is Severity.CRITICAL
    assert set(stack.corticosteroids) == {"prednisone", "methylprednisolone"}


def test_no_findings_steroid_only() -> None:
    assert CorticosteroidNsaidGiBleedPanel().check(medications=_meds("Prednisone")) == []


def test_no_findings_nsaid_only() -> None:
    assert CorticosteroidNsaidGiBleedPanel().check(medications=_meds("Ibuprofen")) == []


def test_whole_token_matching() -> None:
    findings = CorticosteroidNsaidGiBleedPanel().check(
        medications=_meds("Pseudoprednisone", "Ibuprofenx"),
    )
    assert findings == []


def test_deduplicates_same_agent() -> None:
    findings = CorticosteroidNsaidGiBleedPanel().check(
        medications=_meds("Prednisone 10mg", "Prednisone tablet", "Ibuprofen"),
    )
    hit = next(f for f in findings if f.finding_kind == "corticosteroid_nsaid_gi_bleed")
    assert hit.corticosteroids.count("prednisone") == 1


def test_findings_sorted_by_severity() -> None:
    findings = CorticosteroidNsaidGiBleedPanel().check(
        medications=_meds("Prednisone", "Dexamethasone", "Ibuprofen", "Naproxen"),
    )
    assert findings
    rank = {
        Severity.UNKNOWN: 0,
        Severity.LOW: 1,
        Severity.MODERATE: 2,
        Severity.HIGH: 3,
        Severity.CRITICAL: 4,
    }
    scores = [rank[f.severity] for f in findings]
    assert scores == sorted(scores, reverse=True)


def test_never_modifies_medications() -> None:
    meds = _meds("Hydrocortisone", "Diclofenac")
    snapshot = [(m.name, m.model_dump()) for m in meds]
    findings = CorticosteroidNsaidGiBleedPanel().check(medications=meds)
    assert findings
    assert [(m.name, m.model_dump()) for m in meds] == snapshot


def test_exported_from_safety_package() -> None:
    findings = ExportedPanel().check(medications=_meds("Betamethasone", "Celecoxib"))
    assert any(f.finding_kind == "corticosteroid_nsaid_gi_bleed" for f in findings)
    assert all("RESEARCH USE ONLY" in f.rationale for f in findings)
