"""Tests for the SSRI/SNRI + triptan serotonin-syndrome pair checker."""

from __future__ import annotations

from medagent.models import Medication, Severity, SsriTriptanRisk
from medagent.safety import SsriTriptanChecker as ExportedChecker
from medagent.safety.ssri_triptan_checker import SsriTriptanChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    """An SSRI/SNRI or triptan alone yields no finding."""
    checker = SsriTriptanChecker()

    assert checker.check(_meds("Sertraline 50 mg daily")) == []
    assert checker.check(_meds("Sumatriptan 50 mg PRN")) == []
    assert checker.check([]) == []


def test_flags_sertraline_plus_sumatriptan_high() -> None:
    """Sertraline + sumatriptan yields a HIGH research-only finding."""
    findings = SsriTriptanChecker().check(_meds("Sertraline 50 mg daily", "Sumatriptan 50 mg PRN"))

    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, SsriTriptanRisk)
    assert finding.agent == "sertraline"
    assert finding.partner_agent == "sumatriptan"
    assert finding.antidepressant_class == "SSRI"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "serotonin" in finding.rationale.lower()


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
        finding = SsriTriptanChecker().check(
            _meds(f"{agent.title()} 50 mg daily", "Sumatriptan 50 mg PRN")
        )[0]
        assert finding.agent == agent
        assert finding.antidepressant_class == drug_class
        assert finding.partner_agent == "sumatriptan"


def test_all_triptan_panel_agents_participate() -> None:
    """Every supported triptan can produce a finding."""
    triptans = [
        "sumatriptan",
        "rizatriptan",
        "eletriptan",
        "zolmitriptan",
        "naratriptan",
        "almotriptan",
        "frovatriptan",
    ]

    for agent in triptans:
        finding = SsriTriptanChecker().check(
            _meds("Escitalopram 10 mg daily", f"{agent.title()} 5 mg PRN")
        )[0]
        assert finding.partner_agent == agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes do not match either medication panel."""
    checker = SsriTriptanChecker()

    assert checker.check(_meds("Sertralinefree", "Sumatriptanoid")) == []
    assert len(checker.check(_meds("Sertraline 50 mg", "Sumatriptan 50 mg"))) == 1


def test_neighboring_interaction_controls_are_out_of_scope() -> None:
    """Broader serotonin and NSAID+SSRI bleed do not trigger without both classes."""
    checker = SsriTriptanChecker()

    assert checker.check(_meds("Sertraline 50 mg", "Tramadol 50 mg")) == []
    assert checker.check(_meds("Ibuprofen 400 mg", "Sertraline 50 mg")) == []


def test_duplicate_entries_do_not_duplicate_canonical_pairs() -> None:
    """Duplicate entries for the same agents yield one canonical pair."""
    findings = SsriTriptanChecker().check(
        _meds(
            "Sertraline 50 mg daily",
            "Sertraline 100 mg daily",
            "Sumatriptan 50 mg PRN",
            "Sumatriptan 100 mg PRN",
        )
    )

    assert len(findings) == 1


def test_findings_are_deterministic_across_input_order() -> None:
    """Multiple canonical pairs have stable medication/agent ordering."""
    names = [
        "Rizatriptan 10 mg PRN",
        "Sertraline 50 mg daily",
        "Sumatriptan 50 mg PRN",
        "Venlafaxine 75 mg daily",
    ]
    checker = SsriTriptanChecker()

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
        ("sertraline", "rizatriptan"),
        ("sertraline", "sumatriptan"),
        ("venlafaxine", "rizatriptan"),
        ("venlafaxine", "sumatriptan"),
    ]


def test_single_entry_is_not_treated_as_coprescription() -> None:
    """Two class names in one display string do not represent two prescriptions."""
    assert SsriTriptanChecker().check(_meds("Sertraline and sumatriptan interaction note")) == []


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(_meds("Duloxetine 60 mg daily", "Eletriptan 40 mg PRN"))

    assert len(findings) == 1
    assert findings[0].agent == "duloxetine"
    assert findings[0].partner_agent == "eletriptan"
    assert findings[0].antidepressant_class == "SNRI"
