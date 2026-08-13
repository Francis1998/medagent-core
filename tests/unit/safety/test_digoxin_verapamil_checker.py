"""Tests for the digoxin + verapamil toxicity checker."""

from __future__ import annotations

from medagent.models import DigoxinVerapamilRisk, Medication, Severity
from medagent.safety import DigoxinVerapamilChecker as ExportedChecker
from medagent.safety.digoxin_verapamil_checker import DigoxinVerapamilChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    """Digoxin or verapamil alone yields no finding."""
    checker = DigoxinVerapamilChecker()

    assert checker.check(_meds("Digoxin 0.125 mg daily")) == []
    assert checker.check(_meds("Verapamil 120 mg BID")) == []
    assert checker.check([]) == []


def test_flags_digoxin_plus_verapamil_high() -> None:
    """Digoxin + verapamil yields a HIGH research-only finding."""
    findings = DigoxinVerapamilChecker().check(
        _meds("Digoxin 0.125 mg daily", "Verapamil 120 mg BID")
    )

    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, DigoxinVerapamilRisk)
    assert finding.agent == "digoxin"
    assert finding.partner_agent == "verapamil"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "P-glycoprotein" in finding.rationale or "clearance" in finding.rationale.lower()


def test_all_digoxin_panel_agents_participate() -> None:
    """Every supported digoxin agent can produce a finding."""
    for agent in ["digoxin", "lanoxin"]:
        finding = DigoxinVerapamilChecker().check(
            _meds(f"{agent.title()} 0.125 mg daily", "Verapamil 80 mg TID")
        )[0]
        assert finding.agent == agent
        assert finding.partner_agent == "verapamil"


def test_all_verapamil_panel_agents_participate() -> None:
    """Every supported verapamil brand/agent can produce a finding."""
    for agent in ["verapamil", "calan", "isoptin", "verelan"]:
        finding = DigoxinVerapamilChecker().check(
            _meds("Digoxin 0.125 mg daily", f"{agent.title()} 120 mg daily")
        )[0]
        assert finding.partner_agent == agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes do not match either medication panel."""
    checker = DigoxinVerapamilChecker()

    assert checker.check(_meds("Digoxinoid", "Verapamilish")) == []
    assert len(checker.check(_meds("Digoxin 0.125 mg", "Verapamil 120 mg"))) == 1


def test_neighboring_interaction_controls_are_out_of_scope() -> None:
    """Amiodarone and macrolide partners do not trigger without verapamil."""
    checker = DigoxinVerapamilChecker()

    assert checker.check(_meds("Digoxin 0.125 mg", "Amiodarone 200 mg")) == []
    assert checker.check(_meds("Digoxin 0.125 mg", "Clarithromycin 500 mg")) == []


def test_duplicate_entries_do_not_duplicate_canonical_pairs() -> None:
    """Duplicate entries for the same agents yield one canonical pair."""
    findings = DigoxinVerapamilChecker().check(
        _meds(
            "Digoxin 0.125 mg daily",
            "Digoxin 0.25 mg daily",
            "Verapamil 120 mg BID",
            "Verapamil 80 mg TID",
        )
    )

    assert len(findings) == 1


def test_findings_are_deterministic_across_input_order() -> None:
    """Multiple canonical pairs have stable medication/agent ordering."""
    names = [
        "Calan 120 mg daily",
        "Digoxin 0.125 mg daily",
        "Verapamil 80 mg TID",
        "Lanoxin 0.25 mg daily",
    ]
    checker = DigoxinVerapamilChecker()

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
        ("digoxin", "calan"),
        ("digoxin", "verapamil"),
        ("lanoxin", "calan"),
        ("lanoxin", "verapamil"),
    ]


def test_single_entry_is_not_treated_as_coprescription() -> None:
    """Two class names in one display string do not represent two prescriptions."""
    assert DigoxinVerapamilChecker().check(_meds("Digoxin and verapamil interaction note")) == []


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(_meds("Lanoxin 0.125 mg daily", "Isoptin 120 mg daily"))

    assert len(findings) == 1
    assert findings[0].agent == "lanoxin"
    assert findings[0].partner_agent == "isoptin"
