"""Tests for the spironolactone + potassium safety checker."""

from medagent.models import Medication, Severity, SpironolactonePotassiumRisk
from medagent.safety import SpironolactonePotassiumChecker as ExportedChecker
from medagent.safety.spironolactone_potassium_checker import SpironolactonePotassiumChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = SpironolactonePotassiumChecker()
    assert checker.check(_meds("Spironolactone dose")) == []
    assert checker.check(_meds("Potassium chloride dose")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = SpironolactonePotassiumChecker().check(
        _meds("Spironolactone dose", "Potassium chloride dose")
    )[0]
    assert isinstance(finding, SpironolactonePotassiumRisk)
    assert finding.agent == "spironolactone"
    assert finding.partner_agent == "potassium-chloride"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "hyperkalemia" in finding.rationale.lower()


def test_salt_substitute_pair_is_high_not_critical() -> None:
    finding = SpironolactonePotassiumChecker().check(_meds("Aldactone dose", "Salt substitute"))[0]
    assert finding.agent == "aldactone"
    assert finding.partner_agent == "salt-substitute"
    assert finding.severity is Severity.HIGH


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["spironolactone", "aldactone", "eplerenone", "inspra"]:
        finding = SpironolactonePotassiumChecker().check(
            _meds(f"{primary_agent} dose", "KCl dose")
        )[0]
        assert finding.agent == primary_agent
    for partner_agent in [
        "potassium-chloride",
        "kcl",
        "klor-con",
        "potassium",
        "salt-substitute",
        "no-salt",
        "nosalt",
    ]:
        finding = SpironolactonePotassiumChecker().check(
            _meds("Spironolactone dose", f"{partner_agent} dose")
        )[0]
        assert finding.partner_agent == partner_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = SpironolactonePotassiumChecker()
    assert checker.check(_meds("spironolactonelike", "potassiumlike")) == []
    assert len(checker.check(_meds("Spironolactone", "Potassium"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["KCl dose", "Spironolactone dose", "Salt substitute"]
    forward = SpironolactonePotassiumChecker().check(_meds(*names))
    reverse = SpironolactonePotassiumChecker().check(_meds(*reversed(names)))
    assert [(i.agent, i.partner_agent) for i in forward] == [
        (i.agent, i.partner_agent) for i in reverse
    ]
    assert (
        len(
            SpironolactonePotassiumChecker().check(
                _meds("Spironolactone a", "Spironolactone b", "KCl a", "KCl b")
            )
        )
        == 1
    )


def test_findings_sorted_by_severity_first() -> None:
    findings = SpironolactonePotassiumChecker().check(
        _meds("Spironolactone dose", "Salt substitute", "Potassium chloride")
    )
    assert [finding.severity for finding in findings] == [Severity.CRITICAL, Severity.HIGH]
    assert findings[0].partner_agent == "potassium-chloride"
    assert findings[1].partner_agent == "salt-substitute"


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        SpironolactonePotassiumChecker().check(
            _meds("spironolactone and potassium interaction warning")
        )
        == []
    )
    finding = ExportedChecker().check(_meds("Inspra dose", "Klor-Con dose"))[0]
    assert finding.agent == "inspra"
    assert finding.partner_agent == "klor-con"
    assert finding.severity is Severity.CRITICAL
