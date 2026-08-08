"""Tests for the tramadol + SSRI/SNRI seizure/serotonin dual-risk safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import TramadolSsriChecker as ExportedChecker
from medagent.safety.tramadol_ssri_checker import TramadolSsriChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_without_tramadol() -> None:
    """SSRI alone yields no tramadol × SSRI findings."""
    findings = TramadolSsriChecker().check(
        _meds("Sertraline 50 mg daily"),
    )

    assert findings == []


def test_no_findings_with_tramadol_alone() -> None:
    """A lone tramadol without SSRI/SNRI partner yields no findings."""
    findings = TramadolSsriChecker().check(
        _meds("Tramadol 50 mg Q6H"),
    )

    assert findings == []


def test_flags_tramadol_plus_sertraline_high() -> None:
    """Tramadol + sertraline yields a HIGH finding."""
    findings = TramadolSsriChecker().check(
        _meds("Tramadol 50 mg Q6H", "Sertraline 50 mg daily"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "tramadol"
    assert finding.partner_agent == "sertraline"
    assert finding.partner_drug_class == "SSRI"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "seizure" in finding.rationale.lower() or "serotonin" in finding.rationale.lower()


def test_flags_ultram_plus_snri() -> None:
    """Ultram brand + SNRI (venlafaxine/duloxetine) is flagged."""
    findings = TramadolSsriChecker().check(
        _meds("Ultram 50 mg Q6H", "Venlafaxine 75 mg daily"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "ultram"
    assert findings[0].partner_agent == "venlafaxine"
    assert findings[0].partner_drug_class == "SNRI"
    assert findings[0].severity is Severity.HIGH


def test_flags_all_ssri_snri_panel_partners() -> None:
    """Each SSRI/SNRI panel agent pairs with tramadol."""
    partners = [
        ("Fluoxetine 20 mg daily", "fluoxetine", "SSRI"),
        ("Paroxetine 20 mg daily", "paroxetine", "SSRI"),
        ("Citalopram 20 mg daily", "citalopram", "SSRI"),
        ("Escitalopram 10 mg daily", "escitalopram", "SSRI"),
        ("Duloxetine 60 mg daily", "duloxetine", "SNRI"),
    ]
    for med_name, agent, drug_class in partners:
        findings = TramadolSsriChecker().check(
            _meds("Tramadol 50 mg", med_name),
        )
        assert len(findings) == 1, med_name
        assert findings[0].partner_agent == agent
        assert findings[0].partner_drug_class == drug_class


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match panel agents."""
    findings = TramadolSsriChecker().check(
        _meds("Pseudotramadol compound", "Sertraline 50 mg"),
    )

    assert findings == []
    real = TramadolSsriChecker().check(
        _meds("Tramadol 50 mg", "Sertraline 50 mg"),
    )
    assert len(real) == 1


def test_duplicate_medication_entries_do_not_duplicate_pairs() -> None:
    """Duplicate list entries for the same agents do not duplicate pair findings."""
    findings = TramadolSsriChecker().check(
        _meds(
            "Tramadol 50 mg Q6H",
            "Tramadol 100 mg BID",
            "Sertraline 50 mg daily",
        ),
    )

    assert len(findings) == 1


def test_multiple_ssri_partners_produce_multiple_findings() -> None:
    """One tramadol with two SSRI partners yields two findings."""
    findings = TramadolSsriChecker().check(
        _meds(
            "Tramadol 50 mg Q6H",
            "Sertraline 50 mg daily",
            "Fluoxetine 20 mg daily",
        ),
    )

    assert len(findings) == 2
    partner_agents = {finding.partner_agent for finding in findings}
    assert partner_agents == {"sertraline", "fluoxetine"}


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Tramadol 50 mg Q6H", "Sertraline 50 mg daily"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "tramadol"
    assert findings[0].partner_agent == "sertraline"
