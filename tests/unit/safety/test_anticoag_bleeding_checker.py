"""Tests for the anticoagulation bleeding-risk safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import AnticoagBleedingChecker as ExportedChecker
from medagent.safety.anticoag_bleeding_checker import AnticoagBleedingChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_flags_warfarin_aspirin_as_critical() -> None:
    """Warfarin plus aspirin is a CRITICAL anticoagulant × antiplatelet pair."""
    findings = AnticoagBleedingChecker().check(_meds("Warfarin 5mg daily", "Aspirin 81mg"))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.combination_id == "ANTICOAG-BLEED-warfarin-aspirin"
    assert finding.anticoagulant_agent == "warfarin"
    assert finding.augmenter_agent == "aspirin"
    assert finding.augmenter_category == "antiplatelet"
    assert finding.severity is Severity.CRITICAL
    assert "platelet" in finding.mechanism
    assert "hemorrhage" in finding.clinical_consequence
    assert "RESEARCH USE ONLY" in finding.rationale


def test_flags_apixaban_clopidogrel_pair() -> None:
    """DOAC plus P2Y12 inhibitor is flagged as CRITICAL."""
    findings = AnticoagBleedingChecker().check(_meds("Apixaban 5mg BID", "Clopidogrel 75mg daily"))

    assert len(findings) == 1
    assert findings[0].combination_id == "ANTICOAG-BLEED-apixaban-clopidogrel"
    assert findings[0].severity is Severity.CRITICAL


def test_flags_rivaroxaban_ibuprofen_as_high() -> None:
    """Anticoagulant plus NSAID is flagged as HIGH bleeding risk."""
    findings = AnticoagBleedingChecker().check(_meds("Rivaroxaban 20mg", "Ibuprofen 400mg PRN"))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.combination_id == "ANTICOAG-BLEED-rivaroxaban-ibuprofen"
    assert finding.augmenter_category == "NSAID"
    assert finding.severity is Severity.HIGH
    assert "GI" in finding.mechanism or "mucosal" in finding.mechanism


def test_flags_dabigatran_sertraline_as_moderate() -> None:
    """Anticoagulant plus SSRI is flagged as MODERATE bleeding risk."""
    findings = AnticoagBleedingChecker().check(
        _meds("Dabigatran 150mg BID", "Sertraline 50mg daily")
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.combination_id == "ANTICOAG-BLEED-dabigatran-sertraline"
    assert finding.augmenter_category == "SSRI"
    assert finding.severity is Severity.MODERATE


def test_flags_enoxaparin_naproxen_pair() -> None:
    """Low-molecular-weight heparin plus NSAID is flagged."""
    findings = AnticoagBleedingChecker().check(
        _meds("Enoxaparin 40mg SC daily", "Naproxen 500mg BID")
    )

    assert len(findings) == 1
    assert findings[0].anticoagulant_agent == "enoxaparin"
    assert findings[0].augmenter_agent == "naproxen"


def test_flags_heparin_fluoxetine_pair() -> None:
    """Unfractionated heparin plus SSRI is flagged."""
    findings = AnticoagBleedingChecker().check(_meds("Heparin infusion", "Fluoxetine 20mg daily"))

    assert len(findings) == 1
    assert findings[0].anticoagulant_agent == "heparin"
    assert findings[0].augmenter_agent == "fluoxetine"


def test_anticoagulant_alone_yields_no_findings() -> None:
    """A lone anticoagulant does not trigger bleeding-risk pair findings."""
    findings = AnticoagBleedingChecker().check(_meds("Warfarin 5mg daily", "Lisinopril 10mg"))

    assert findings == []


def test_augmenter_alone_yields_no_findings() -> None:
    """A lone antiplatelet or NSAID without anticoagulation is not flagged."""
    findings = AnticoagBleedingChecker().check(_meds("Aspirin 81mg", "Sertraline 50mg"))

    assert findings == []


def test_duplicate_agent_entries_do_not_duplicate_pair_findings() -> None:
    """Brand/generic double-listing of one agent should not duplicate findings."""
    findings = AnticoagBleedingChecker().check(
        _meds("Warfarin 5mg", "warfarin tablet", "Aspirin 81mg")
    )

    assert len(findings) == 1
    assert findings[0].combination_id == "ANTICOAG-BLEED-warfarin-aspirin"


def test_single_medication_entry_naming_both_agents_is_not_a_pair_by_itself() -> None:
    """A combination requires two active medication entries, not one descriptive string."""
    findings = AnticoagBleedingChecker().check(_meds("warfarin-aspirin research blend"))

    assert findings == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not trigger bleeding-risk pair findings."""
    findings = AnticoagBleedingChecker().check(
        _meds("Pseudowarfarin tonic", "Aspirinoid compound", "Ibuprofenlike gel")
    )

    assert findings == []
    real = AnticoagBleedingChecker().check(_meds("Warfarin 5mg", "Aspirin 81mg"))
    assert len(real) == 1


def test_multiple_pairs_are_all_reported() -> None:
    """Each distinct anticoagulant × augmenter pair across meds is reported."""
    findings = AnticoagBleedingChecker().check(
        _meds("Warfarin 5mg", "Aspirin 81mg", "Sertraline 50mg")
    )

    assert len(findings) == 2
    combination_ids = {finding.combination_id for finding in findings}
    assert combination_ids == {
        "ANTICOAG-BLEED-warfarin-aspirin",
        "ANTICOAG-BLEED-warfarin-sertraline",
    }


def test_findings_ordered_by_descending_severity_then_combination_id() -> None:
    """CRITICAL antiplatelet pairs sort before MODERATE SSRI pairs."""
    findings = AnticoagBleedingChecker().check(
        _meds("Warfarin 5mg", "Sertraline 50mg", "Aspirin 81mg")
    )

    assert [finding.severity for finding in findings] == [
        Severity.CRITICAL,
        Severity.MODERATE,
    ]
    assert findings[0].combination_id == "ANTICOAG-BLEED-warfarin-aspirin"
    assert findings[1].combination_id == "ANTICOAG-BLEED-warfarin-sertraline"


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(_meds("Apixaban 5mg", "Ibuprofen 400mg"))

    assert len(findings) == 1
    assert findings[0].combination_id == "ANTICOAG-BLEED-apixaban-ibuprofen"
