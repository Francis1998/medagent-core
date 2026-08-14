"""Tests for the ACE inhibitor + sacubitril/Entresto checker."""

from __future__ import annotations

from medagent.models import AceiSacubitrilRisk, Medication, Severity
from medagent.safety import AceiSacubitrilChecker as ExportedChecker
from medagent.safety.acei_sacubitril_checker import AceiSacubitrilChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    """An ACE inhibitor or sacubitril alone yields no finding."""
    checker = AceiSacubitrilChecker()

    assert checker.check(_meds("Lisinopril 10 mg daily")) == []
    assert checker.check(_meds("Entresto 24/26 mg BID")) == []
    assert checker.check([]) == []


def test_flags_lisinopril_plus_entresto_critical() -> None:
    """Lisinopril + Entresto yields a CRITICAL research-only finding."""
    findings = AceiSacubitrilChecker().check(
        _meds("Lisinopril 10 mg daily", "Entresto 24/26 mg BID")
    )

    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, AceiSacubitrilRisk)
    assert finding.agent == "lisinopril"
    assert finding.partner_agent == "entresto"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "36-hour" in finding.rationale
    assert "angioedema" in finding.rationale.lower()


def test_sacubitril_generic_is_detected() -> None:
    """The generic sacubitril token is detected independently of the brand."""
    finding = AceiSacubitrilChecker().check(
        _meds("Enalapril 5 mg daily", "Sacubitril/valsartan 49/51 mg BID")
    )[0]

    assert finding.agent == "enalapril"
    assert finding.partner_agent == "sacubitril"
    assert finding.severity is Severity.CRITICAL


def test_all_supported_ace_inhibitors_participate() -> None:
    """Every requested ACE inhibitor can produce a finding."""
    acei_agents = [
        "lisinopril",
        "enalapril",
        "ramipril",
        "benazepril",
        "quinapril",
        "captopril",
        "fosinopril",
        "perindopril",
        "trandolapril",
        "moexipril",
    ]

    for acei_agent in acei_agents:
        finding = AceiSacubitrilChecker().check(
            _meds(f"{acei_agent.title()} 10 mg daily", "Entresto 24/26 mg BID")
        )[0]
        assert finding.agent == acei_agent
        assert finding.severity is Severity.CRITICAL


def test_neighboring_acei_arb_duplication_is_out_of_scope() -> None:
    """An ACEI + ARB pair without sacubitril does not trigger this control."""
    checker = AceiSacubitrilChecker()

    assert checker.check(_meds("Lisinopril 10 mg daily", "Losartan 50 mg daily")) == []
    assert checker.check(_meds("Lisinopril 10 mg daily", "Valsartan 80 mg daily")) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes do not match either medication panel."""
    checker = AceiSacubitrilChecker()

    assert checker.check(_meds("Lisinopriloid", "Entrestoid")) == []
    assert len(checker.check(_meds("Lisinopril 10 mg", "Entresto 24/26 mg"))) == 1


def test_duplicate_entries_do_not_duplicate_canonical_pairs() -> None:
    """Duplicate entries for the same agents yield one canonical pair."""
    findings = AceiSacubitrilChecker().check(
        _meds(
            "Lisinopril 10 mg daily",
            "Lisinopril 20 mg daily",
            "Entresto 24/26 mg BID",
            "Entresto 49/51 mg BID",
        )
    )

    assert len(findings) == 1


def test_findings_are_deterministic_across_input_order() -> None:
    """Multiple canonical pairs have stable medication and agent ordering."""
    names = [
        "Sacubitril 49 mg BID",
        "Lisinopril 10 mg daily",
        "Entresto 24/26 mg BID",
        "Enalapril 5 mg daily",
    ]
    checker = AceiSacubitrilChecker()

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
    assert [(finding.agent, finding.partner_agent) for finding in forward] == [
        ("enalapril", "entresto"),
        ("enalapril", "sacubitril"),
        ("lisinopril", "entresto"),
        ("lisinopril", "sacubitril"),
    ]


def test_single_entry_is_not_treated_as_coprescription() -> None:
    """Two class names in one display string do not represent two prescriptions."""
    assert AceiSacubitrilChecker().check(_meds("Lisinopril and Entresto interaction note")) == []


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    finding = ExportedChecker().check(_meds("Ramipril 5 mg daily", "Entresto 24/26 mg BID"))[0]

    assert finding.agent == "ramipril"
    assert finding.partner_agent == "entresto"
    assert finding.severity is Severity.CRITICAL
