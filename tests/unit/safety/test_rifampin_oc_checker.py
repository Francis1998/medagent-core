"""Tests for the Rifampin + Oral Contraceptive safety checker."""

from medagent.models import Medication, RifampinOcRisk, Severity
from medagent.safety import RifampinOcChecker as ExportedChecker
from medagent.safety.rifampin_oc_checker import RifampinOcChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = RifampinOcChecker()
    assert checker.check(_meds("rifampin dose")) == []
    assert checker.check(_meds("ethinylestradiol dose")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    checker = RifampinOcChecker()
    finding = checker.check(_meds("rifampin dose", "ethinylestradiol dose"))[0]
    assert isinstance(finding, RifampinOcRisk)
    assert finding.agent == "rifampin"
    assert finding.partner_agent == "ethinylestradiol"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale


def test_all_supported_agents_participate() -> None:
    checker = RifampinOcChecker()
    for primary_agent in ["rifampin", "rifampicin", "rifadin", "rimactane"]:
        finding = checker.check(_meds(f"{primary_agent} dose", "ethinylestradiol dose"))[0]
        assert finding.agent == primary_agent
    for partner_agent in [
        "ethinylestradiol",
        "levonorgestrel",
        "norethindrone",
        "desogestrel",
    ]:
        finding = checker.check(_meds("rifampin dose", f"{partner_agent} dose"))[0]
        assert finding.partner_agent == partner_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = RifampinOcChecker()
    assert checker.check(_meds("rifampinlike", "ethinylestradiollike")) == []
    assert len(checker.check(_meds("rifampin", "ethinylestradiol"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["ethinylestradiol dose", "rifampin dose", "levonorgestrel dose"]
    checker = RifampinOcChecker()
    forward = checker.check(_meds(*names))
    reverse = checker.check(_meds(*reversed(names)))
    assert [(i.agent, i.partner_agent) for i in forward] == [
        (i.agent, i.partner_agent) for i in reverse
    ]
    assert (
        len(
            checker.check(
                _meds(
                    "rifampin a",
                    "rifampin b",
                    "ethinylestradiol a",
                    "ethinylestradiol b",
                )
            )
        )
        == 1
    )


def test_export_alias_matches() -> None:
    assert ExportedChecker is RifampinOcChecker


def test_rationale_mentions_research_only() -> None:
    finding = RifampinOcChecker().check(_meds("rifampin", "ethinylestradiol"))[0]
    assert finding.rationale.startswith("RESEARCH USE ONLY")


def test_severity_ordering_stable() -> None:
    findings = RifampinOcChecker().check(_meds("rifampin", "ethinylestradiol"))
    assert findings
    ranks = {Severity.HIGH: 3, Severity.CRITICAL: 4}
    assert ranks[findings[0].severity] >= 3
