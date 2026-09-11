"""Tests for polypharmacy deprescribe suggester (HITL candidates, any age)."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import PolypharmacyDeprescribeSuggester as ExportedSuggester
from medagent.safety.polypharmacy_deprescribe_suggester import (
    PolypharmacyDeprescribeSuggester,
)


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_duplicate_therapy_deprescribe_candidate() -> None:
    findings = PolypharmacyDeprescribeSuggester().check(
        medications=_meds("Sertraline 50mg", "Fluoxetine 20mg"),
    )
    hit = next(f for f in findings if f.finding_kind == "duplicate_therapy_deprescribe_candidate")
    assert set(hit.candidate_stops) == {"fluoxetine", "sertraline"}
    assert hit.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never auto-stops" in hit.rationale or "never auto-stops" in hit.rationale.lower()


def test_high_burden_deprescribe_candidate() -> None:
    findings = PolypharmacyDeprescribeSuggester().check(
        medications=_meds("Amitriptyline", "Oxybutynin", "Diphenhydramine"),
    )
    hit = next(f for f in findings if f.finding_kind == "high_burden_deprescribe_candidate")
    assert set(hit.candidate_stops) == {"amitriptyline", "diphenhydramine", "oxybutynin"}
    assert hit.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in hit.rationale


def test_sliding_scale_insulin_deprescribe_candidate() -> None:
    findings = PolypharmacyDeprescribeSuggester().check(
        medications=[
            Medication(name="Insulin lispro", frequency="sliding scale AC"),
        ],
    )
    hit = next(
        f for f in findings if f.finding_kind == "sliding_scale_insulin_deprescribe_candidate"
    )
    assert hit.candidate_stops
    assert "insulin" in hit.candidate_stops or "lispro" in hit.candidate_stops
    assert "RESEARCH USE ONLY" in hit.rationale


def test_ppi_without_indication_deprescribe_candidate() -> None:
    findings = PolypharmacyDeprescribeSuggester().check(
        medications=_meds("Omeprazole 20mg"),
        indications=[],
    )
    hit = next(
        f for f in findings if f.finding_kind == "ppi_without_indication_deprescribe_candidate"
    )
    assert hit.candidate_stops == ["omeprazole"]
    assert hit.severity is Severity.LOW


def test_ppi_with_indication_suppressed() -> None:
    findings = PolypharmacyDeprescribeSuggester().check(
        medications=_meds("Pantoprazole"),
        indications=["Barrett esophagus surveillance"],
    )
    assert all(f.finding_kind != "ppi_without_indication_deprescribe_candidate" for f in findings)


def test_polypharmacy_count_candidate() -> None:
    findings = PolypharmacyDeprescribeSuggester().check(
        medications=_meds("A", "B", "C", "D", "E"),
    )
    hit = next(f for f in findings if f.finding_kind == "polypharmacy_count_candidate")
    assert hit.severity is Severity.MODERATE
    assert len(hit.medication_names) == 5
    assert hit.candidate_stops == []


def test_polypharmacy_count_high_threshold() -> None:
    names = [f"Med{i}" for i in range(10)]
    findings = PolypharmacyDeprescribeSuggester().check(medications=_meds(*names))
    hit = next(f for f in findings if f.finding_kind == "polypharmacy_count_candidate")
    assert hit.severity is Severity.HIGH


def test_not_age_gated_unlike_geriatric_checker() -> None:
    """Polypharmacy suggester fires for any age; geriatric checker is age>=65."""
    findings = PolypharmacyDeprescribeSuggester().check(
        medications=_meds("Sertraline", "Fluoxetine", "Omeprazole"),
    )
    kinds = {f.finding_kind for f in findings}
    assert "duplicate_therapy_deprescribe_candidate" in kinds
    assert "ppi_without_indication_deprescribe_candidate" in kinds


def test_no_findings_for_benign_short_list() -> None:
    findings = PolypharmacyDeprescribeSuggester().check(
        medications=_meds("Metformin", "Lisinopril"),
    )
    assert findings == []


def test_whole_token_matching() -> None:
    findings = PolypharmacyDeprescribeSuggester().check(
        medications=_meds("Sertralinex", "Fluoxetineade", "Omeprazolex"),
    )
    assert findings == []


def test_findings_sorted_by_severity() -> None:
    findings = PolypharmacyDeprescribeSuggester().check(
        medications=_meds(
            "Amitriptyline",
            "Oxybutynin",
            "Diphenhydramine",
            "Sertraline",
            "Fluoxetine",
            "Omeprazole",
            "A",
            "B",
            "C",
            "D",
            "E",
        ),
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
    meds = _meds("Sertraline", "Fluoxetine", "Omeprazole")
    snapshot = [m.model_dump() for m in meds]
    findings = PolypharmacyDeprescribeSuggester().check(medications=meds)
    assert findings
    assert [m.model_dump() for m in meds] == snapshot
    assert all("RESEARCH USE ONLY" in f.rationale for f in findings)
    assert all(
        "never auto-stops" in f.rationale.lower() or "Never auto-stops" in f.rationale
        for f in findings
    )


def test_exported_from_safety_package() -> None:
    findings = ExportedSuggester().check(
        medications=_meds("Lisinopril", "Enalapril"),
    )
    assert any(f.finding_kind == "duplicate_therapy_deprescribe_candidate" for f in findings)
    assert all("RESEARCH USE ONLY" in f.rationale for f in findings)
