"""Tests for the lithium + thiazide diuretic checker."""

from medagent.models import LithiumThiazideRisk, Medication, Severity
from medagent.safety import LithiumThiazideChecker as ExportedChecker
from medagent.safety.lithium_thiazide_checker import LithiumThiazideChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = LithiumThiazideChecker()
    assert checker.check(_meds("Lithium 300 mg BID")) == []
    assert checker.check(_meds("Hydrochlorothiazide 25 mg daily")) == []
    assert checker.check([]) == []


def test_flags_lithium_plus_hydrochlorothiazide_high() -> None:
    finding = LithiumThiazideChecker().check(
        _meds("Lithium 300 mg BID", "Hydrochlorothiazide 25 mg daily")
    )[0]

    assert isinstance(finding, LithiumThiazideRisk)
    assert finding.agent == "lithium"
    assert finding.partner_agent == "hydrochlorothiazide"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "renal lithium clearance" in finding.rationale


def test_all_supported_agents_participate() -> None:
    for lithium_agent in ["lithium", "lithobid", "eskalith"]:
        finding = LithiumThiazideChecker().check(
            _meds(f"{lithium_agent.title()} 300 mg", "HCTZ 25 mg")
        )[0]
        assert finding.agent == lithium_agent

    for thiazide_agent in [
        "hctz",
        "hydrochlorothiazide",
        "chlorthalidone",
        "indapamide",
    ]:
        finding = LithiumThiazideChecker().check(
            _meds("Lithium 300 mg", f"{thiazide_agent.title()} 25 mg")
        )[0]
        assert finding.partner_agent == thiazide_agent
        assert finding.severity is Severity.HIGH


def test_non_thiazide_diuretics_are_out_of_scope() -> None:
    checker = LithiumThiazideChecker()
    for diuretic in ["Furosemide", "Spironolactone", "Amiloride"]:
        assert checker.check(_meds("Lithium 300 mg", diuretic)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = LithiumThiazideChecker()
    assert checker.check(_meds("Lithiumlike", "Hctzfree")) == []
    assert len(checker.check(_meds("Lithium", "HCTZ"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = [
        "Indapamide 2.5 mg",
        "Lithium 300 mg",
        "Chlorthalidone 25 mg",
    ]
    forward = LithiumThiazideChecker().check(_meds(*names))
    reverse = LithiumThiazideChecker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert [item.partner_agent for item in forward] == [
        "chlorthalidone",
        "indapamide",
    ]
    assert (
        len(
            LithiumThiazideChecker().check(
                _meds(
                    "Lithium 300 mg",
                    "Lithium 150 mg",
                    "HCTZ 25 mg",
                    "HCTZ 12.5 mg",
                )
            )
        )
        == 1
    )


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert LithiumThiazideChecker().check(_meds("Lithium and HCTZ interaction warning")) == []
    finding = ExportedChecker().check(_meds("Lithobid 300 mg", "Indapamide 2.5 mg"))[0]
    assert finding.agent == "lithobid"
    assert finding.partner_agent == "indapamide"
