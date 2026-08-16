"""Tests for the linezolid + SSRI/SNRI safety checker."""

from medagent.models import LinezolidSsriRisk, Medication, Severity
from medagent.safety import LinezolidSsriChecker as ExportedChecker
from medagent.safety.linezolid_ssri_checker import LinezolidSsriChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = LinezolidSsriChecker()
    assert checker.check(_meds("Linezolid 600 mg BID")) == []
    assert checker.check(_meds("Sertraline 50 mg daily")) == []
    assert checker.check([]) == []


def test_flags_linezolid_plus_sertraline_critical() -> None:
    finding = LinezolidSsriChecker().check(_meds("Linezolid 600 mg BID", "Sertraline 50 mg daily"))[
        0
    ]
    assert isinstance(finding, LinezolidSsriRisk)
    assert finding.agent == "linezolid"
    assert finding.partner_agent == "sertraline"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "serotonin syndrome" in finding.rationale.lower()


def test_all_supported_ssri_snri_agents_participate() -> None:
    for partner in [
        "sertraline",
        "fluoxetine",
        "paroxetine",
        "citalopram",
        "escitalopram",
        "venlafaxine",
        "duloxetine",
    ]:
        finding = LinezolidSsriChecker().check(
            _meds("Linezolid 600 mg", f"{partner.title()} 20 mg")
        )[0]
        assert finding.partner_agent == partner
        assert finding.severity is Severity.CRITICAL


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = LinezolidSsriChecker()
    assert checker.check(_meds("Linezolide analog", "Sertralineish")) == []
    assert len(checker.check(_meds("Linezolid", "Escitalopram"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Venlafaxine 75 mg", "Linezolid 600 mg", "Duloxetine 30 mg"]
    forward = LinezolidSsriChecker().check(_meds(*names))
    reverse = LinezolidSsriChecker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent) for item in forward] == [
        (item.agent, item.partner_agent) for item in reverse
    ]
    assert [item.partner_agent for item in forward] == ["duloxetine", "venlafaxine"]
    assert (
        len(
            LinezolidSsriChecker().check(
                _meds("Linezolid", "Linezolid 600 mg", "Sertraline", "Sertraline 50 mg")
            )
        )
        == 1
    )


def test_single_entry_is_not_coprescription() -> None:
    assert LinezolidSsriChecker().check(_meds("Linezolid and sertraline warning")) == []


def test_checker_is_exported_from_safety_package() -> None:
    finding = ExportedChecker().check(_meds("Linezolid", "Fluoxetine"))[0]
    assert finding.partner_agent == "fluoxetine"
