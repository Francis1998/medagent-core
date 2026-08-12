"""Tests for the fluoroquinolone + NSAID CNS / seizure-risk checker."""

from __future__ import annotations

from medagent.models import FluoroquinoloneNsaidRisk, Medication, Severity
from medagent.safety import FluoroquinoloneNsaidChecker as ExportedChecker
from medagent.safety.fluoroquinolone_nsaid_checker import FluoroquinoloneNsaidChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    """A fluoroquinolone or NSAID alone yields no finding."""
    checker = FluoroquinoloneNsaidChecker()

    assert checker.check(_meds("Ciprofloxacin 500 mg BID")) == []
    assert checker.check(_meds("Ibuprofen 400 mg TID")) == []
    assert checker.check([]) == []


def test_flags_ciprofloxacin_plus_ibuprofen_high() -> None:
    """Ciprofloxacin + ibuprofen yields a HIGH research-only finding."""
    findings = FluoroquinoloneNsaidChecker().check(
        _meds("Ciprofloxacin 500 mg BID", "Ibuprofen 400 mg TID")
    )

    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, FluoroquinoloneNsaidRisk)
    assert finding.agent == "ciprofloxacin"
    assert finding.partner_agent == "ibuprofen"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "seizure" in finding.rationale.lower() or "cns" in finding.rationale.lower()


def test_all_fluoroquinolone_panel_agents_participate() -> None:
    """Every supported fluoroquinolone can produce a finding."""
    fluoroquinolones = ["ciprofloxacin", "levofloxacin", "moxifloxacin", "ofloxacin"]

    for agent in fluoroquinolones:
        finding = FluoroquinoloneNsaidChecker().check(
            _meds(f"{agent.title()} 500 mg daily", "Naproxen 500 mg BID")
        )[0]
        assert finding.agent == agent
        assert finding.partner_agent == "naproxen"


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
        finding = FluoroquinoloneNsaidChecker().check(
            _meds("Levofloxacin 750 mg daily", f"{agent.title()} 200 mg daily")
        )[0]
        assert finding.partner_agent == agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes do not match either medication panel."""
    checker = FluoroquinoloneNsaidChecker()

    assert checker.check(_meds("Ciprofloxacinoid", "Ibuprofenfree")) == []
    assert len(checker.check(_meds("Ciprofloxacin 500 mg", "Ibuprofen 400 mg"))) == 1


def test_neighboring_interaction_controls_are_out_of_scope() -> None:
    """FQ+warfarin and warfarin+NSAID do not trigger without both target classes."""
    checker = FluoroquinoloneNsaidChecker()

    assert checker.check(_meds("Ciprofloxacin 500 mg", "Warfarin 5 mg")) == []
    assert checker.check(_meds("Warfarin 5 mg", "Ibuprofen 400 mg")) == []


def test_duplicate_entries_do_not_duplicate_canonical_pairs() -> None:
    """Duplicate entries for the same agents yield one canonical pair."""
    findings = FluoroquinoloneNsaidChecker().check(
        _meds(
            "Ciprofloxacin 500 mg BID",
            "Ciprofloxacin 250 mg BID",
            "Ibuprofen 400 mg TID",
            "Ibuprofen 200 mg TID",
        )
    )

    assert len(findings) == 1


def test_findings_are_deterministic_across_input_order() -> None:
    """Multiple canonical pairs have stable medication/agent ordering."""
    names = [
        "Naproxen 500 mg BID",
        "Ciprofloxacin 500 mg BID",
        "Ibuprofen 400 mg TID",
        "Levofloxacin 750 mg daily",
    ]
    checker = FluoroquinoloneNsaidChecker()

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
        ("ciprofloxacin", "ibuprofen"),
        ("ciprofloxacin", "naproxen"),
        ("levofloxacin", "ibuprofen"),
        ("levofloxacin", "naproxen"),
    ]


def test_single_entry_is_not_treated_as_coprescription() -> None:
    """Two class names in one display string do not represent two prescriptions."""
    assert (
        FluoroquinoloneNsaidChecker().check(_meds("Ciprofloxacin and ibuprofen interaction note"))
        == []
    )


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(_meds("Moxifloxacin 400 mg daily", "Diclofenac 50 mg BID"))

    assert len(findings) == 1
    assert findings[0].agent == "moxifloxacin"
    assert findings[0].partner_agent == "diclofenac"
