"""Tests for the carbamazepine + CYP3A4-inhibiting macrolide checker."""

from medagent.models import CarbamazepineMacrolideRisk, Medication, Severity
from medagent.safety import CarbamazepineMacrolideChecker as ExportedChecker
from medagent.safety.carbamazepine_macrolide_checker import CarbamazepineMacrolideChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = CarbamazepineMacrolideChecker()
    assert checker.check(_meds("Carbamazepine 200 mg BID")) == []
    assert checker.check(_meds("Clarithromycin 500 mg BID")) == []
    assert checker.check([]) == []


def test_flags_carbamazepine_plus_clarithromycin_high() -> None:
    finding = CarbamazepineMacrolideChecker().check(
        _meds("Carbamazepine 200 mg BID", "Clarithromycin 500 mg BID")
    )[0]

    assert isinstance(finding, CarbamazepineMacrolideRisk)
    assert finding.agent == "carbamazepine"
    assert finding.partner_agent == "clarithromycin"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "CYP3A4" in finding.rationale


def test_all_supported_agents_participate() -> None:
    for carbamazepine_agent in ["carbamazepine", "tegretol", "carbatrol", "equetro"]:
        finding = CarbamazepineMacrolideChecker().check(
            _meds(f"{carbamazepine_agent.title()} 200 mg", "Clarithromycin 500 mg")
        )[0]
        assert finding.agent == carbamazepine_agent

    for macrolide_agent in ["clarithromycin", "erythromycin"]:
        finding = CarbamazepineMacrolideChecker().check(
            _meds("Carbamazepine 200 mg", f"{macrolide_agent.title()} 500 mg")
        )[0]
        assert finding.partner_agent == macrolide_agent
        assert finding.severity is Severity.HIGH


def test_azithromycin_is_out_of_scope() -> None:
    assert (
        CarbamazepineMacrolideChecker().check(
            _meds("Carbamazepine 200 mg BID", "Azithromycin 500 mg daily")
        )
        == []
    )


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = CarbamazepineMacrolideChecker()
    assert checker.check(_meds("Carbamazepinelike", "Clarithromycinoid")) == []
    assert len(checker.check(_meds("Carbamazepine", "Clarithromycin"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = [
        "Erythromycin 250 mg",
        "Tegretol 200 mg",
        "Carbamazepine 100 mg",
        "Clarithromycin 500 mg",
    ]
    forward = CarbamazepineMacrolideChecker().check(_meds(*names))
    reverse = CarbamazepineMacrolideChecker().check(_meds(*reversed(names)))

    assert [
        (item.medication, item.partner_medication, item.agent, item.partner_agent)
        for item in forward
    ] == [
        (item.medication, item.partner_medication, item.agent, item.partner_agent)
        for item in reverse
    ]
    assert [(item.agent, item.partner_agent) for item in forward] == [
        ("carbamazepine", "clarithromycin"),
        ("carbamazepine", "erythromycin"),
        ("tegretol", "clarithromycin"),
        ("tegretol", "erythromycin"),
    ]
    assert (
        len(
            CarbamazepineMacrolideChecker().check(
                _meds(
                    "Carbamazepine 200 mg",
                    "Carbamazepine 100 mg",
                    "Erythromycin 250 mg",
                    "Erythromycin 500 mg",
                )
            )
        )
        == 1
    )


def test_single_entry_is_not_coprescription() -> None:
    assert (
        CarbamazepineMacrolideChecker().check(
            _meds("Carbamazepine and clarithromycin interaction warning")
        )
        == []
    )


def test_checker_is_exported_from_safety_package() -> None:
    finding = ExportedChecker().check(_meds("Carbatrol 200 mg", "Erythromycin 250 mg"))[0]
    assert finding.agent == "carbatrol"
    assert finding.partner_agent == "erythromycin"
