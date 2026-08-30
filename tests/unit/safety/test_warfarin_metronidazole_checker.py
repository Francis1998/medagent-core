"""Tests for the warfarin + metronidazole safety checker."""

from medagent.models import Medication, Severity, WarfarinMetronidazoleRisk
from medagent.safety import WarfarinMetronidazoleChecker as ExportedChecker
from medagent.safety.warfarin_metronidazole_checker import WarfarinMetronidazoleChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = WarfarinMetronidazoleChecker()
    assert checker.check(_meds("Warfarin dose")) == []
    assert checker.check(_meds("Metronidazole dose")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = WarfarinMetronidazoleChecker().check(
        _meds("Warfarin dose", "Metronidazole dose")
    )[0]
    assert isinstance(finding, WarfarinMetronidazoleRisk)
    assert finding.agent == "warfarin"
    assert finding.partner_agent == "metronidazole"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "INR" in finding.rationale


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["warfarin", "coumadin", "jantoven"]:
        finding = WarfarinMetronidazoleChecker().check(
            _meds(f"{primary_agent} dose", "Metronidazole dose")
        )[0]
        assert finding.agent == primary_agent
    for partner_agent in ["metronidazole", "flagyl"]:
        finding = WarfarinMetronidazoleChecker().check(
            _meds("Warfarin dose", f"{partner_agent} dose")
        )[0]
        assert finding.partner_agent == partner_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = WarfarinMetronidazoleChecker()
    assert checker.check(_meds("warfarinlike", "metronidazolefree")) == []
    assert len(checker.check(_meds("Warfarin", "Metronidazole"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Flagyl dose", "Warfarin dose", "Metronidazole dose"]
    forward = WarfarinMetronidazoleChecker().check(_meds(*names))
    reverse = WarfarinMetronidazoleChecker().check(_meds(*reversed(names)))
    assert [(i.agent, i.partner_agent) for i in forward] == [
        (i.agent, i.partner_agent) for i in reverse
    ]
    assert (
        len(
            WarfarinMetronidazoleChecker().check(
                _meds("Warfarin a", "Warfarin b", "Metronidazole a", "Metronidazole b")
            )
        )
        == 1
    )


def test_findings_sorted_deterministically_by_partner() -> None:
    findings = WarfarinMetronidazoleChecker().check(
        _meds("Warfarin dose", "Flagyl dose", "Metronidazole dose")
    )
    assert [f.partner_agent for f in findings] == sorted(f.partner_agent for f in findings)


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        WarfarinMetronidazoleChecker().check(
            _meds("warfarin and metronidazole interaction warning")
        )
        == []
    )
    finding = ExportedChecker().check(_meds("Jantoven dose", "Flagyl dose"))[0]
    assert finding.agent == "jantoven"
    assert finding.partner_agent == "flagyl"
