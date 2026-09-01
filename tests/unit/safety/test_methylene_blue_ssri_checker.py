"""Tests for the Methylene Blue + SSRI/SNRI safety checker."""

from medagent.models import Medication, MethyleneBlueSsriRisk, Severity
from medagent.safety import MethyleneBlueSsriChecker as ExportedChecker
from medagent.safety.methylene_blue_ssri_checker import MethyleneBlueSsriChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = MethyleneBlueSsriChecker()
    assert checker.check(_meds("methylene-blue dose")) == []
    assert checker.check(_meds("sertraline dose")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    checker = MethyleneBlueSsriChecker()
    finding = checker.check(_meds("methylene-blue dose", "sertraline dose"))[0]
    assert isinstance(finding, MethyleneBlueSsriRisk)
    assert finding.agent == "methylene-blue"
    assert finding.partner_agent == "sertraline"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale


def test_all_supported_agents_participate() -> None:
    checker = MethyleneBlueSsriChecker()
    for primary_agent in [
        "methylene-blue",
        "methylthioninium",
        "provayblue",
    ]:
        finding = checker.check(_meds(f"{primary_agent} dose", "sertraline dose"))[0]
        assert finding.agent == primary_agent
    for partner_agent in [
        "sertraline",
        "zoloft",
        "fluoxetine",
        "prozac",
        "paroxetine",
        "paxil",
        "citalopram",
        "escitalopram",
        "lexapro",
        "venlafaxine",
        "effexor",
        "duloxetine",
        "cymbalta",
    ]:
        finding = checker.check(_meds("methylene-blue dose", f"{partner_agent} dose"))[0]
        assert finding.partner_agent == partner_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = MethyleneBlueSsriChecker()
    assert checker.check(_meds("methylene-bluelike", "sertralinelike")) == []
    assert len(checker.check(_meds("methylene-blue", "sertraline"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["sertraline dose", "methylene-blue dose", "zoloft dose"]
    checker = MethyleneBlueSsriChecker()
    forward = checker.check(_meds(*names))
    reverse = checker.check(_meds(*reversed(names)))
    assert [(i.agent, i.partner_agent) for i in forward] == [
        (i.agent, i.partner_agent) for i in reverse
    ]
    assert (
        len(
            checker.check(
                _meds("methylene-blue a", "methylene-blue b", "sertraline a", "sertraline b")
            )
        )
        == 1
    )


def test_export_alias_matches() -> None:
    assert ExportedChecker is MethyleneBlueSsriChecker


def test_rationale_mentions_research_only() -> None:
    finding = MethyleneBlueSsriChecker().check(_meds("methylene-blue", "sertraline"))[0]
    assert finding.rationale.startswith("RESEARCH USE ONLY")


def test_severity_ordering_stable() -> None:
    findings = MethyleneBlueSsriChecker().check(_meds("methylene-blue", "sertraline"))
    assert findings
    ranks = {Severity.HIGH: 3, Severity.CRITICAL: 4}
    assert ranks[findings[0].severity] >= 3
