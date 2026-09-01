"""Tests for the Amlodipine + Clarithromycin safety checker."""

from medagent.models import AmlodipineClarithromycinRisk, Medication, Severity
from medagent.safety import AmlodipineClarithromycinChecker as ExportedChecker
from medagent.safety.amlodipine_clarithromycin_checker import (
    AmlodipineClarithromycinChecker,
)


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = AmlodipineClarithromycinChecker()
    assert checker.check(_meds("amlodipine dose")) == []
    assert checker.check(_meds("clarithromycin dose")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    checker = AmlodipineClarithromycinChecker()
    finding = checker.check(_meds("amlodipine dose", "clarithromycin dose"))[0]
    assert isinstance(finding, AmlodipineClarithromycinRisk)
    assert finding.agent == "amlodipine"
    assert finding.partner_agent == "clarithromycin"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale


def test_all_supported_agents_participate() -> None:
    checker = AmlodipineClarithromycinChecker()
    for primary_agent in ["amlodipine", "norvasc"]:
        finding = checker.check(_meds(f"{primary_agent} dose", "clarithromycin dose"))[0]
        assert finding.agent == primary_agent
    for partner_agent in ["clarithromycin", "biaxin"]:
        finding = checker.check(_meds("amlodipine dose", f"{partner_agent} dose"))[0]
        assert finding.partner_agent == partner_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = AmlodipineClarithromycinChecker()
    assert checker.check(_meds("amlodipinelike", "clarithromycinlike")) == []
    assert len(checker.check(_meds("amlodipine", "clarithromycin"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["clarithromycin dose", "amlodipine dose", "biaxin dose"]
    checker = AmlodipineClarithromycinChecker()
    forward = checker.check(_meds(*names))
    reverse = checker.check(_meds(*reversed(names)))
    assert [(i.agent, i.partner_agent) for i in forward] == [
        (i.agent, i.partner_agent) for i in reverse
    ]
    assert (
        len(
            checker.check(
                _meds(
                    "amlodipine a",
                    "amlodipine b",
                    "clarithromycin a",
                    "clarithromycin b",
                )
            )
        )
        == 1
    )


def test_export_alias_matches() -> None:
    assert ExportedChecker is AmlodipineClarithromycinChecker


def test_rationale_mentions_research_only() -> None:
    finding = AmlodipineClarithromycinChecker().check(_meds("amlodipine", "clarithromycin"))[0]
    assert finding.rationale.startswith("RESEARCH USE ONLY")


def test_severity_ordering_stable() -> None:
    findings = AmlodipineClarithromycinChecker().check(_meds("amlodipine", "clarithromycin"))
    assert findings
    ranks = {Severity.HIGH: 3, Severity.CRITICAL: 4}
    assert ranks[findings[0].severity] >= 3
