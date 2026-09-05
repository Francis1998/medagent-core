"""Tests for the Ethinylestradiol + Lamotrigine Level Reduction Risk safety checker."""

from medagent.models import EthinylestradiolLamotrigineRisk, Medication, Severity
from medagent.safety import EthinylestradiolLamotrigineChecker as ExportedChecker
from medagent.safety.ethinylestradiol_lamotrigine_checker import EthinylestradiolLamotrigineChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = EthinylestradiolLamotrigineChecker()
    assert checker.check(_meds("lamotrigine dose")) == []
    assert checker.check(_meds("ethinylestradiol dose")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    checker = EthinylestradiolLamotrigineChecker()
    finding = checker.check(_meds("lamotrigine dose", "ethinylestradiol dose"))[0]
    assert isinstance(finding, EthinylestradiolLamotrigineRisk)
    assert finding.agent == "lamotrigine"
    assert finding.partner_agent == "ethinylestradiol"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale


def test_all_supported_agents_participate() -> None:
    checker = EthinylestradiolLamotrigineChecker()
    for primary_agent in ["lamotrigine", "lamictal"]:
        finding = checker.check(_meds(f"{primary_agent} dose", "ethinylestradiol dose"))[0]
        assert finding.agent == primary_agent
    for partner_agent in ["ethinylestradiol", "ethinyloestradiol", "ethinyl", "yaz", "yasmin"]:
        finding = checker.check(_meds("lamotrigine dose", f"{partner_agent} dose"))[0]
        assert finding.partner_agent == partner_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = EthinylestradiolLamotrigineChecker()
    assert checker.check(_meds("lamotriginelike", "ethinylestradiollike")) == []
    assert len(checker.check(_meds("lamotrigine", "ethinylestradiol"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["ethinylestradiol dose", "lamotrigine dose"]
    if len(["lamotrigine", "lamictal"]) > 1:
        names.append("lamictal dose")
    checker = EthinylestradiolLamotrigineChecker()
    forward = checker.check(_meds(*names))
    reverse = checker.check(_meds(*reversed(names)))
    assert [(i.agent, i.partner_agent) for i in forward] == [
        (i.agent, i.partner_agent) for i in reverse
    ]
    assert (
        len(
            checker.check(
                _meds(
                    "lamotrigine a",
                    "lamotrigine b",
                    "ethinylestradiol a",
                    "ethinylestradiol b",
                )
            )
        )
        == 1
    )


def test_export_alias_matches() -> None:
    assert ExportedChecker is EthinylestradiolLamotrigineChecker


def test_rationale_mentions_research_only() -> None:
    finding = EthinylestradiolLamotrigineChecker().check(_meds("lamotrigine", "ethinylestradiol"))[
        0
    ]
    assert finding.rationale.startswith("RESEARCH USE ONLY")


def test_severity_ordering_stable() -> None:
    findings = EthinylestradiolLamotrigineChecker().check(_meds("lamotrigine", "ethinylestradiol"))
    assert findings
    ranks = {Severity.HIGH: 3, Severity.CRITICAL: 4, Severity.MODERATE: 2}
    assert ranks[findings[0].severity] >= 2
