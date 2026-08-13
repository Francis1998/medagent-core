"""Tests for the statin + macrolide CYP3A4 interaction checker."""

from __future__ import annotations

from medagent.models import Medication, Severity, StatinMacrolideRisk
from medagent.safety import StatinMacrolideChecker as ExportedChecker
from medagent.safety.statin_macrolide_checker import StatinMacrolideChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    """A statin or macrolide alone yields no finding."""
    checker = StatinMacrolideChecker()

    assert checker.check(_meds("Simvastatin 40 mg nightly")) == []
    assert checker.check(_meds("Clarithromycin 500 mg BID")) == []
    assert checker.check([]) == []


def test_flags_simvastatin_plus_clarithromycin_critical() -> None:
    """Simvastatin + clarithromycin yields a CRITICAL research-only finding."""
    findings = StatinMacrolideChecker().check(
        _meds("Simvastatin 40 mg nightly", "Clarithromycin 500 mg BID")
    )

    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, StatinMacrolideRisk)
    assert finding.agent == "simvastatin"
    assert finding.partner_agent == "clarithromycin"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "CYP3A4" in finding.rationale


def test_lovastatin_is_critical_and_atorvastatin_is_high() -> None:
    """Lovastatin is CRITICAL; atorvastatin is HIGH with strong macrolides."""
    lovastatin = StatinMacrolideChecker().check(
        _meds("Lovastatin 40 mg nightly", "Erythromycin 250 mg QID")
    )[0]
    atorvastatin = StatinMacrolideChecker().check(
        _meds("Atorvastatin 40 mg nightly", "Clarithromycin 500 mg BID")
    )[0]

    assert lovastatin.severity is Severity.CRITICAL
    assert atorvastatin.severity is Severity.HIGH


def test_all_statin_panel_agents_participate() -> None:
    """Every supported statin can produce a finding."""
    for agent in ["simvastatin", "lovastatin", "atorvastatin"]:
        finding = StatinMacrolideChecker().check(
            _meds(f"{agent.title()} 20 mg nightly", "Clarithromycin 500 mg BID")
        )[0]
        assert finding.agent == agent
        assert finding.partner_agent == "clarithromycin"


def test_all_macrolide_panel_agents_participate() -> None:
    """Every supported strong CYP3A4 macrolide can produce a finding."""
    for agent in ["clarithromycin", "erythromycin"]:
        finding = StatinMacrolideChecker().check(
            _meds("Simvastatin 20 mg nightly", f"{agent.title()} 500 mg")
        )[0]
        assert finding.partner_agent == agent


def test_azithromycin_is_out_of_scope() -> None:
    """Azithromycin is intentionally excluded as a weaker CYP3A4 inhibitor."""
    assert (
        StatinMacrolideChecker().check(
            _meds("Simvastatin 40 mg nightly", "Azithromycin 500 mg daily")
        )
        == []
    )


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes do not match either medication panel."""
    checker = StatinMacrolideChecker()

    assert checker.check(_meds("Simvastatinoid", "Clarithromycinish")) == []
    assert len(checker.check(_meds("Simvastatin 20 mg", "Clarithromycin 500 mg"))) == 1


def test_neighboring_interaction_controls_are_out_of_scope() -> None:
    """Broader CYP3A4 inhibitors outside the macrolide panel do not trigger."""
    checker = StatinMacrolideChecker()

    assert checker.check(_meds("Simvastatin 20 mg", "Itraconazole 200 mg")) == []
    assert checker.check(_meds("Simvastatin 20 mg", "Ritonavir 100 mg")) == []


def test_duplicate_entries_do_not_duplicate_canonical_pairs() -> None:
    """Duplicate entries for the same agents yield one canonical pair."""
    findings = StatinMacrolideChecker().check(
        _meds(
            "Simvastatin 20 mg nightly",
            "Simvastatin 40 mg nightly",
            "Clarithromycin 250 mg BID",
            "Clarithromycin 500 mg BID",
        )
    )

    assert len(findings) == 1


def test_findings_are_deterministic_across_input_order() -> None:
    """Multiple canonical pairs have stable medication/agent ordering."""
    names = [
        "Erythromycin 250 mg QID",
        "Simvastatin 40 mg nightly",
        "Clarithromycin 500 mg BID",
        "Atorvastatin 20 mg nightly",
    ]
    checker = StatinMacrolideChecker()

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
    assert [(finding.agent, finding.partner_agent, finding.severity) for finding in forward] == [
        ("simvastatin", "clarithromycin", Severity.CRITICAL),
        ("simvastatin", "erythromycin", Severity.CRITICAL),
        ("atorvastatin", "clarithromycin", Severity.HIGH),
        ("atorvastatin", "erythromycin", Severity.HIGH),
    ]


def test_single_entry_is_not_treated_as_coprescription() -> None:
    """Two class names in one display string do not represent two prescriptions."""
    assert (
        StatinMacrolideChecker().check(_meds("Simvastatin and clarithromycin interaction note"))
        == []
    )


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(_meds("Lovastatin 40 mg nightly", "Erythromycin 250 mg QID"))

    assert len(findings) == 1
    assert findings[0].agent == "lovastatin"
    assert findings[0].partner_agent == "erythromycin"
    assert findings[0].severity is Severity.CRITICAL
