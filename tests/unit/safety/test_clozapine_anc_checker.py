"""Tests for the clozapine ANC monitoring safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import ClozapineAncChecker as ExportedChecker
from medagent.safety.clozapine_anc_checker import ClozapineAncChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_without_clozapine() -> None:
    """Non-clozapine medications yield no ANC monitoring findings."""
    findings = ClozapineAncChecker().check(
        _meds("Olanzapine 10 mg daily", "Sertraline 50 mg daily"),
    )

    assert findings == []


def test_flags_clozapine_critical_monitoring() -> None:
    """Clozapine alone yields a CRITICAL ANC monitoring finding."""
    findings = ClozapineAncChecker().check(
        _meds("Clozapine 200 mg BID"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "clozapine"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "anc" in finding.rationale.lower() or "neutrophil" in finding.rationale.lower()
    assert "agranulocytosis" in finding.rationale.lower()


def test_flags_clozaril_and_fazaclo_brands() -> None:
    """Clozaril and FazaClo brand formulations are flagged for ANC monitoring."""
    findings = ClozapineAncChecker().check(
        _meds("Clozaril 100 mg BID"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "clozaril"
    assert findings[0].severity is Severity.CRITICAL

    findings_fazaclo = ClozapineAncChecker().check(
        _meds("FazaClo 25 mg daily"),
    )
    assert len(findings_fazaclo) == 1
    assert findings_fazaclo[0].agent == "fazaclo"
    assert findings_fazaclo[0].severity is Severity.CRITICAL


def test_always_emits_even_when_anc_cue_present() -> None:
    """ANC monitoring reminder is emitted even if ANC language appears nearby."""
    findings = ClozapineAncChecker().check(
        _meds("Clozapine 150 mg BID", "ANC monitoring per REMS"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "clozapine"


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match clozapine-class agents."""
    findings = ClozapineAncChecker().check(
        _meds("Pseudoclozapine compound", "Clozarilfree tablet"),
    )

    assert findings == []
    real = ClozapineAncChecker().check(
        _meds("Clozapine 100 mg"),
    )
    assert len(real) == 1


def test_duplicate_medication_entries_do_not_duplicate_findings() -> None:
    """Duplicate clozapine entries do not duplicate findings for the same agent."""
    findings = ClozapineAncChecker().check(
        _meds(
            "Clozapine 100 mg BID",
            "Clozapine 200 mg BID",
        ),
    )

    assert len(findings) == 1


def test_multiple_brand_agents_produce_multiple_findings() -> None:
    """Distinct clozapine-class agents each produce a finding."""
    findings = ClozapineAncChecker().check(
        _meds("Clozapine 100 mg", "Clozaril 50 mg"),
    )

    assert len(findings) == 2
    agents = {finding.agent for finding in findings}
    assert agents == {"clozapine", "clozaril"}
    # Deterministic ordering: medication name then agent.
    assert [(f.medication.lower(), f.agent) for f in findings] == sorted(
        (f.medication.lower(), f.agent) for f in findings
    )


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Clozapine 200 mg BID"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "clozapine"
