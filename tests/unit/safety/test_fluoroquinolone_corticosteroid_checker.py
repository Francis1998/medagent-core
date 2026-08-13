"""Tests for the fluoroquinolone + corticosteroid tendon-risk checker."""

from __future__ import annotations

from medagent.models import FluoroquinoloneCorticosteroidRisk, Medication, Severity
from medagent.safety import FluoroquinoloneCorticosteroidChecker as ExportedChecker
from medagent.safety.fluoroquinolone_corticosteroid_checker import (
    FluoroquinoloneCorticosteroidChecker,
)


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    """A fluoroquinolone or corticosteroid alone yields no finding."""
    checker = FluoroquinoloneCorticosteroidChecker()

    assert checker.check(_meds("Ciprofloxacin 500 mg BID")) == []
    assert checker.check(_meds("Prednisone 20 mg daily")) == []
    assert checker.check([]) == []


def test_flags_ciprofloxacin_plus_prednisone_high() -> None:
    """Ciprofloxacin + prednisone yields a HIGH research-only finding."""
    findings = FluoroquinoloneCorticosteroidChecker().check(
        _meds("Ciprofloxacin 500 mg BID", "Prednisone 20 mg daily")
    )

    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, FluoroquinoloneCorticosteroidRisk)
    assert finding.agent == "ciprofloxacin"
    assert finding.partner_agent == "prednisone"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "tendon" in finding.rationale.lower()


def test_all_fluoroquinolone_panel_agents_participate() -> None:
    """Every supported fluoroquinolone can produce a finding."""
    for agent in ["ciprofloxacin", "levofloxacin", "moxifloxacin", "ofloxacin"]:
        finding = FluoroquinoloneCorticosteroidChecker().check(
            _meds(f"{agent.title()} 500 mg", "Prednisone 10 mg daily")
        )[0]
        assert finding.agent == agent
        assert finding.partner_agent == "prednisone"


def test_all_corticosteroid_panel_agents_participate() -> None:
    """Every supported corticosteroid can produce a finding."""
    steroids = [
        "prednisone",
        "prednisolone",
        "methylprednisolone",
        "dexamethasone",
        "hydrocortisone",
        "betamethasone",
    ]

    for agent in steroids:
        finding = FluoroquinoloneCorticosteroidChecker().check(
            _meds("Levofloxacin 750 mg daily", f"{agent.title()} 4 mg daily")
        )[0]
        assert finding.partner_agent == agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes do not match either medication panel."""
    checker = FluoroquinoloneCorticosteroidChecker()

    assert checker.check(_meds("Ciprofloxacinkit", "Prednisonoid")) == []
    assert len(checker.check(_meds("Ciprofloxacin 500 mg", "Prednisone 10 mg"))) == 1


def test_neighboring_interaction_controls_are_out_of_scope() -> None:
    """FQ+NSAID and FQ+warfarin partners do not trigger without corticosteroids."""
    checker = FluoroquinoloneCorticosteroidChecker()

    assert checker.check(_meds("Ciprofloxacin 500 mg", "Ibuprofen 400 mg")) == []
    assert checker.check(_meds("Ciprofloxacin 500 mg", "Warfarin 5 mg")) == []


def test_duplicate_entries_do_not_duplicate_canonical_pairs() -> None:
    """Duplicate entries for the same agents yield one canonical pair."""
    findings = FluoroquinoloneCorticosteroidChecker().check(
        _meds(
            "Ciprofloxacin 500 mg BID",
            "Ciprofloxacin 250 mg BID",
            "Prednisone 20 mg daily",
            "Prednisone 10 mg daily",
        )
    )

    assert len(findings) == 1


def test_findings_are_deterministic_across_input_order() -> None:
    """Multiple canonical pairs have stable medication/agent ordering."""
    names = [
        "Prednisone 20 mg daily",
        "Ciprofloxacin 500 mg BID",
        "Dexamethasone 4 mg daily",
        "Levofloxacin 750 mg daily",
    ]
    checker = FluoroquinoloneCorticosteroidChecker()

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
        ("ciprofloxacin", "dexamethasone"),
        ("ciprofloxacin", "prednisone"),
        ("levofloxacin", "dexamethasone"),
        ("levofloxacin", "prednisone"),
    ]


def test_single_entry_is_not_treated_as_coprescription() -> None:
    """Two class names in one display string do not represent two prescriptions."""
    assert (
        FluoroquinoloneCorticosteroidChecker().check(
            _meds("Ciprofloxacin and prednisone interaction note")
        )
        == []
    )


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Moxifloxacin 400 mg daily", "Methylprednisolone 16 mg daily")
    )

    assert len(findings) == 1
    assert findings[0].agent == "moxifloxacin"
    assert findings[0].partner_agent == "methylprednisolone"
