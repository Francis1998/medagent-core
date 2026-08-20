"""Tests for the warfarin + metronidazole/tinidazole checker."""

from medagent.models import Medication, Severity, WarfarinMetronidazoleRisk
from medagent.safety import WarfarinMetronidazoleChecker as ExportedChecker
from medagent.safety.warfarin_metronidazole_checker import (
    WarfarinMetronidazoleChecker,
)


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = WarfarinMetronidazoleChecker()
    assert checker.check(_meds("Warfarin 5 mg daily")) == []
    assert checker.check(_meds("Metronidazole 500 mg BID")) == []
    assert checker.check([]) == []


def test_flags_warfarin_plus_metronidazole_high() -> None:
    finding = WarfarinMetronidazoleChecker().check(
        _meds("Warfarin 5 mg daily", "Metronidazole 500 mg BID")
    )[0]

    assert isinstance(finding, WarfarinMetronidazoleRisk)
    assert finding.agent == "warfarin"
    assert finding.partner_agent == "metronidazole"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "CYP2C9" in finding.rationale
    assert "INR" in finding.rationale


def test_all_supported_agents_participate() -> None:
    for warfarin_agent in ["warfarin", "coumadin", "jantoven"]:
        finding = WarfarinMetronidazoleChecker().check(
            _meds(f"{warfarin_agent.title()} 5 mg", "Metronidazole 500 mg")
        )[0]
        assert finding.agent == warfarin_agent

    for antibiotic_agent in ["metronidazole", "tinidazole"]:
        finding = WarfarinMetronidazoleChecker().check(
            _meds("Warfarin 5 mg", f"{antibiotic_agent.title()} 500 mg")
        )[0]
        assert finding.partner_agent == antibiotic_agent
        assert finding.severity is Severity.HIGH


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = WarfarinMetronidazoleChecker()
    assert checker.check(_meds("Warfarinlike", "Metronidazolefree")) == []
    assert len(checker.check(_meds("Warfarin", "Metronidazole"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Tinidazole 500 mg", "Warfarin 5 mg", "Metronidazole 500 mg"]
    forward = WarfarinMetronidazoleChecker().check(_meds(*names))
    reverse = WarfarinMetronidazoleChecker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert [item.partner_agent for item in forward] == [
        "metronidazole",
        "tinidazole",
    ]
    assert (
        len(
            WarfarinMetronidazoleChecker().check(
                _meds(
                    "Warfarin 5 mg",
                    "Warfarin 2 mg",
                    "Metronidazole 500 mg",
                    "Metronidazole 250 mg",
                )
            )
        )
        == 1
    )


def test_single_entry_is_not_coprescription() -> None:
    assert (
        WarfarinMetronidazoleChecker().check(
            _meds("Warfarin and metronidazole interaction warning")
        )
        == []
    )


def test_checker_is_exported_from_safety_package() -> None:
    finding = ExportedChecker().check(_meds("Jantoven 5 mg", "Tinidazole 500 mg"))[0]
    assert finding.agent == "jantoven"
    assert finding.partner_agent == "tinidazole"
