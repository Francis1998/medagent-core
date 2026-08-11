"""Tests for the NSAID + SSRI/SNRI bleeding-intensifier checker."""

from __future__ import annotations

from medagent.models import Medication, NsaidSsriBleedRisk, Severity
from medagent.safety import NsaidSsriBleedChecker as ExportedChecker
from medagent.safety.nsaid_ssri_checker import NsaidSsriBleedChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    """An NSAID or SSRI/SNRI alone yields no finding."""
    checker = NsaidSsriBleedChecker()

    assert checker.check(_meds("Ibuprofen 400 mg TID")) == []
    assert checker.check(_meds("Sertraline 50 mg daily")) == []
    assert checker.check([]) == []


def test_flags_ibuprofen_plus_sertraline_high() -> None:
    """Ibuprofen + sertraline yields a HIGH research-only finding."""
    findings = NsaidSsriBleedChecker().check(
        _meds("Ibuprofen 400 mg TID", "Sertraline 50 mg daily")
    )

    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, NsaidSsriBleedRisk)
    assert finding.agent == "ibuprofen"
    assert finding.partner_agent == "sertraline"
    assert finding.partner_drug_class == "SSRI"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "bleeding" in finding.rationale.lower()


def test_all_nsaid_panel_agents_participate() -> None:
    """Every supported NSAID can produce a finding."""
    nsaids = [
        "ibuprofen",
        "naproxen",
        "diclofenac",
        "ketorolac",
        "meloxicam",
        "celecoxib",
        "indomethacin",
        "piroxicam",
        "aspirin",
    ]

    for agent in nsaids:
        finding = NsaidSsriBleedChecker().check(
            _meds(f"{agent.title()} 200 mg daily", "Sertraline 50 mg daily")
        )[0]
        assert finding.agent == agent
        assert finding.partner_agent == "sertraline"


def test_all_ssri_snri_panel_agents_participate() -> None:
    """Every supported SSRI and SNRI can produce a finding."""
    antidepressants = {
        "sertraline": "SSRI",
        "fluoxetine": "SSRI",
        "paroxetine": "SSRI",
        "citalopram": "SSRI",
        "escitalopram": "SSRI",
        "fluvoxamine": "SSRI",
        "venlafaxine": "SNRI",
        "desvenlafaxine": "SNRI",
        "duloxetine": "SNRI",
        "levomilnacipran": "SNRI",
        "milnacipran": "SNRI",
    }

    for agent, drug_class in antidepressants.items():
        finding = NsaidSsriBleedChecker().check(
            _meds("Naproxen 500 mg BID", f"{agent.title()} 50 mg daily")
        )[0]
        assert finding.partner_agent == agent
        assert finding.partner_drug_class == drug_class


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes do not match either medication panel."""
    checker = NsaidSsriBleedChecker()

    assert checker.check(_meds("Ibuprofenoid", "Sertralinefree")) == []
    assert len(checker.check(_meds("Ibuprofen 400 mg", "Sertraline 50 mg"))) == 1


def test_neighboring_interaction_controls_are_out_of_scope() -> None:
    """Warfarin+NSAID and tramadol+SSRI do not trigger without both target classes."""
    checker = NsaidSsriBleedChecker()

    assert checker.check(_meds("Warfarin 5 mg", "Ibuprofen 400 mg")) == []
    assert checker.check(_meds("Tramadol 50 mg", "Sertraline 50 mg")) == []


def test_duplicate_entries_do_not_duplicate_canonical_pairs() -> None:
    """Duplicate entries for the same agents yield one canonical pair."""
    findings = NsaidSsriBleedChecker().check(
        _meds(
            "Diclofenac 50 mg BID",
            "Diclofenac 25 mg BID",
            "Duloxetine 60 mg daily",
            "Duloxetine 30 mg daily",
        )
    )

    assert len(findings) == 1


def test_findings_are_deterministic_across_input_order() -> None:
    """Multiple canonical pairs have stable medication/agent ordering."""
    names = [
        "Sertraline 50 mg daily",
        "Naproxen 500 mg BID",
        "Duloxetine 60 mg daily",
        "Ibuprofen 400 mg TID",
    ]
    checker = NsaidSsriBleedChecker()

    forward = checker.check(_meds(*names))
    reverse = checker.check(_meds(*reversed(names)))

    forward_pairs = [
        (finding.medication, finding.partner_medication, finding.agent, finding.partner_agent)
        for finding in forward
    ]
    reverse_pairs = [
        (finding.medication, finding.partner_medication, finding.agent, finding.partner_agent)
        for finding in reverse
    ]
    assert forward_pairs == reverse_pairs
    assert [(finding.agent, finding.partner_agent) for finding in forward] == [
        ("ibuprofen", "duloxetine"),
        ("ibuprofen", "sertraline"),
        ("naproxen", "duloxetine"),
        ("naproxen", "sertraline"),
    ]


def test_single_entry_is_not_treated_as_coprescription() -> None:
    """Two class names in one display string do not represent two prescriptions."""
    assert NsaidSsriBleedChecker().check(_meds("Ibuprofen and sertraline interaction note")) == []


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(_meds("Meloxicam 15 mg daily", "Venlafaxine 75 mg daily"))

    assert len(findings) == 1
    assert findings[0].agent == "meloxicam"
    assert findings[0].partner_agent == "venlafaxine"
    assert findings[0].partner_drug_class == "SNRI"
