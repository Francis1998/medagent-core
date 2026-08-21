"""Tests for the tramadol + bupropion seizure-risk checker."""

from medagent.models import Medication, Severity, TramadolBupropionRisk
from medagent.safety import TramadolBupropionChecker as ExportedChecker
from medagent.safety.tramadol_bupropion_checker import TramadolBupropionChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = TramadolBupropionChecker()
    assert checker.check(_meds("Tramadol 50 mg")) == []
    assert checker.check(_meds("Bupropion XL 150 mg")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = TramadolBupropionChecker().check(_meds("Tramadol 50 mg", "Bupropion XL 150 mg"))[0]

    assert isinstance(finding, TramadolBupropionRisk)
    assert finding.agent == "tramadol"
    assert finding.partner_agent == "bupropion"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "lower the seizure threshold" in finding.rationale


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["tramadol", "ultram"]:
        finding = TramadolBupropionChecker().check(
            _meds(f"{primary_agent} dose", "Bupropion XL 150 mg")
        )[0]
        assert finding.agent == primary_agent

    for partner_agent in ["bupropion", "wellbutrin", "zyban"]:
        finding = TramadolBupropionChecker().check(
            _meds("Tramadol 50 mg", f"{partner_agent} dose")
        )[0]
        assert finding.partner_agent == partner_agent
        assert finding.severity is Severity.HIGH


def test_related_but_out_of_scope_agents_do_not_flag() -> None:
    checker = TramadolBupropionChecker()
    for agent in ["Sertraline", "Fluoxetine", "Venlafaxine"]:
        assert checker.check(_meds("Tramadol 50 mg", agent)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = TramadolBupropionChecker()
    assert checker.check(_meds("Tramadollike", "Bupropionfree")) == []
    assert len(checker.check(_meds("Ultram", "Wellbutrin"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Zyban 150 mg", "Tramadol 50 mg", "Wellbutrin XL 150 mg"]
    forward = TramadolBupropionChecker().check(_meds(*names))
    reverse = TramadolBupropionChecker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert [item.partner_agent for item in forward] == ["wellbutrin", "zyban"]
    assert (
        len(
            TramadolBupropionChecker().check(
                _meds(
                    "Tramadol 50 mg",
                    "Tramadol 50 mg",
                    "Bupropion XL 150 mg",
                    "Bupropion XL 150 mg",
                )
            )
        )
        == 1
    )


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        TramadolBupropionChecker().check(_meds("Ultram and Wellbutrin interaction warning")) == []
    )
    finding = ExportedChecker().check(_meds("Ultram", "Wellbutrin"))[0]
    assert finding.severity is Severity.HIGH
