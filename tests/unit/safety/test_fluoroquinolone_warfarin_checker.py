"""Tests for the fluoroquinolone + warfarin INR/bleeding safety checker."""

from __future__ import annotations

from medagent.models import FluoroquinoloneWarfarinRisk, Medication, Severity
from medagent.safety import FluoroquinoloneWarfarinChecker as ExportedChecker
from medagent.safety.fluoroquinolone_warfarin_checker import (
    FluoroquinoloneWarfarinChecker,
)


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    """A fluoroquinolone or warfarin alone yields no finding."""
    checker = FluoroquinoloneWarfarinChecker()

    assert checker.check(_meds("Ciprofloxacin 500 mg BID")) == []
    assert checker.check(_meds("Warfarin 5 mg daily")) == []
    assert checker.check([]) == []


def test_flags_ciprofloxacin_plus_warfarin_high() -> None:
    """Ciprofloxacin + warfarin yields a HIGH research-only finding."""
    findings = FluoroquinoloneWarfarinChecker().check(
        _meds("Ciprofloxacin 500 mg BID", "Warfarin 5 mg daily")
    )

    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, FluoroquinoloneWarfarinRisk)
    assert finding.agent == "ciprofloxacin"
    assert finding.partner_agent == "warfarin"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "inr" in finding.rationale.lower()
    assert "bleeding" in finding.rationale.lower()


def test_all_panel_agents_participate() -> None:
    """Every fluoroquinolone and warfarin-class agent can produce a finding."""
    fluoroquinolones = ["ciprofloxacin", "levofloxacin", "moxifloxacin", "ofloxacin"]
    warfarins = ["warfarin", "coumadin", "jantoven"]

    for agent in fluoroquinolones:
        finding = FluoroquinoloneWarfarinChecker().check(
            _meds(f"{agent.title()} 500 mg", "Coumadin 5 mg daily")
        )[0]
        assert finding.agent == agent
        assert finding.partner_agent == "coumadin"

    for agent in warfarins:
        finding = FluoroquinoloneWarfarinChecker().check(
            _meds("Levofloxacin 500 mg daily", f"{agent.title()} 5 mg")
        )[0]
        assert finding.partner_agent == agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes do not match either medication panel."""
    checker = FluoroquinoloneWarfarinChecker()

    assert checker.check(_meds("Ciprofloxacinoid", "Warfarinoid")) == []
    assert len(checker.check(_meds("Ciprofloxacin 500 mg", "Warfarin 5 mg"))) == 1


def test_duplicate_entries_do_not_duplicate_canonical_pairs() -> None:
    """Duplicate entries for the same agents yield one canonical pair."""
    findings = FluoroquinoloneWarfarinChecker().check(
        _meds(
            "Ciprofloxacin 500 mg BID",
            "Ciprofloxacin 250 mg BID",
            "Warfarin 5 mg daily",
            "Warfarin 2.5 mg daily",
        )
    )

    assert len(findings) == 1


def test_findings_are_deterministic_across_input_order() -> None:
    """Multiple canonical pairs have stable medication/agent ordering."""
    names = [
        "Warfarin 5 mg daily",
        "Moxifloxacin 400 mg daily",
        "Coumadin 2 mg daily",
        "Ciprofloxacin 500 mg BID",
    ]
    checker = FluoroquinoloneWarfarinChecker()

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
    assert [finding.agent for finding in forward] == [
        "ciprofloxacin",
        "ciprofloxacin",
        "moxifloxacin",
        "moxifloxacin",
    ]


def test_single_entry_is_not_treated_as_coprescription() -> None:
    """Two class names in one display string do not represent two prescriptions."""
    assert (
        FluoroquinoloneWarfarinChecker().check(_meds("Ciprofloxacin and warfarin interaction note"))
        == []
    )


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(_meds("Ofloxacin 400 mg daily", "Jantoven 5 mg daily"))

    assert len(findings) == 1
    assert findings[0].agent == "ofloxacin"
    assert findings[0].partner_agent == "jantoven"
