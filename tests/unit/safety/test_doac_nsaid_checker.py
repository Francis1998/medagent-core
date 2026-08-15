"""Tests for the DOAC + NSAID bleeding intensifier safety checker."""

from __future__ import annotations

from medagent.models import DoacNsaidRisk, Medication, Severity
from medagent.safety import DoacNsaidChecker as ExportedChecker
from medagent.safety.doac_nsaid_checker import DoacNsaidChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    """DOAC or an NSAID alone yields no finding."""
    checker = DoacNsaidChecker()

    assert checker.check(_meds("Apixaban 5 mg BID")) == []
    assert checker.check(_meds("Ibuprofen 400 mg PRN")) == []
    assert checker.check([]) == []


def test_flags_apixaban_plus_ibuprofen_high() -> None:
    """Apixaban + ibuprofen yields a HIGH research-only finding."""
    findings = DoacNsaidChecker().check(_meds("Apixaban 5 mg BID", "Ibuprofen 400 mg TID"))

    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, DoacNsaidRisk)
    assert finding.agent == "apixaban"
    assert finding.partner_agent == "ibuprofen"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "bleeding" in finding.rationale.lower()


def test_ketorolac_escalates_to_critical() -> None:
    """Ketorolac with a DOAC yields CRITICAL severity."""
    finding = DoacNsaidChecker().check(_meds("Rivaroxaban 20 mg daily", "Ketorolac 30 mg IM"))[0]

    assert finding.agent == "rivaroxaban"
    assert finding.partner_agent == "ketorolac"
    assert finding.severity is Severity.CRITICAL


def test_all_supported_agents_participate() -> None:
    """Every supported DOAC and NSAID token can produce a finding."""
    for doac_agent in ["apixaban", "rivaroxaban", "edoxaban", "dabigatran"]:
        finding = DoacNsaidChecker().check(_meds(f"{doac_agent.title()} 5 mg", "Ibuprofen 400 mg"))[
            0
        ]
        assert finding.agent == doac_agent

    for nsaid_agent in [
        "ibuprofen",
        "naproxen",
        "diclofenac",
        "ketorolac",
        "meloxicam",
        "celecoxib",
    ]:
        finding = DoacNsaidChecker().check(_meds("Apixaban 5 mg", f"{nsaid_agent.title()} 200 mg"))[
            0
        ]
        assert finding.partner_agent == nsaid_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes do not match either medication panel."""
    checker = DoacNsaidChecker()

    assert checker.check(_meds("Pseudoapixaban compound", "Ibuprofenoid supplement")) == []
    assert len(checker.check(_meds("Apixaban 5 mg", "Ibuprofen 400 mg"))) == 1


def test_duplicate_entries_do_not_duplicate_canonical_pairs() -> None:
    """Duplicate entries for the same agents yield one canonical pair."""
    findings = DoacNsaidChecker().check(
        _meds(
            "Apixaban 2.5 mg BID",
            "Apixaban 5 mg BID",
            "Ibuprofen 200 mg",
            "Ibuprofen 400 mg",
        )
    )

    assert len(findings) == 1


def test_findings_are_deterministic_across_input_order() -> None:
    """Multiple canonical pairs have stable severity and medication ordering."""
    names = [
        "Naproxen 500 mg BID",
        "Ketorolac 30 mg IM",
        "Apixaban 5 mg BID",
        "Meloxicam 15 mg daily",
    ]
    checker = DoacNsaidChecker()

    forward = checker.check(_meds(*names))
    reverse = checker.check(_meds(*reversed(names)))

    forward_values = [
        (
            finding.medication,
            finding.partner_medication,
            finding.agent,
            finding.partner_agent,
            finding.severity,
        )
        for finding in forward
    ]
    reverse_values = [
        (
            finding.medication,
            finding.partner_medication,
            finding.agent,
            finding.partner_agent,
            finding.severity,
        )
        for finding in reverse
    ]
    assert forward_values == reverse_values
    assert len(forward) == 3
    assert [(finding.partner_agent, finding.severity) for finding in forward] == [
        ("ketorolac", Severity.CRITICAL),
        ("meloxicam", Severity.HIGH),
        ("naproxen", Severity.HIGH),
    ]


def test_single_entry_is_not_treated_as_coprescription() -> None:
    """Two class names in one display string do not represent two prescriptions."""
    assert DoacNsaidChecker().check(_meds("Apixaban and ibuprofen interaction note")) == []


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    finding = ExportedChecker().check(_meds("Edoxaban 60 mg daily", "Diclofenac 50 mg"))[0]

    assert finding.agent == "edoxaban"
    assert finding.partner_agent == "diclofenac"
    assert finding.severity is Severity.HIGH
