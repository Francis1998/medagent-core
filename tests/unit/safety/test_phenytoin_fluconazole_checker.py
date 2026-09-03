"""Tests for the Phenytoin + Fluconazole safety checker."""

from medagent.models import Medication, PhenytoinFluconazoleRisk, Severity
from medagent.safety import PhenytoinFluconazoleChecker as ExportedChecker
from medagent.safety.phenytoin_fluconazole_checker import PhenytoinFluconazoleChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = PhenytoinFluconazoleChecker()
    assert checker.check(_meds("phenytoin dose")) == []
    assert checker.check(_meds("fluconazole dose")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    checker = PhenytoinFluconazoleChecker()
    finding = checker.check(_meds("phenytoin dose", "fluconazole dose"))[0]
    assert isinstance(finding, PhenytoinFluconazoleRisk)
    assert finding.agent == "phenytoin"
    assert finding.partner_agent == "fluconazole"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale


def test_all_supported_agents_participate() -> None:
    checker = PhenytoinFluconazoleChecker()
    for primary_agent in ["phenytoin", "dilantin", "phenytek", "fosphenytoin", "cerebyx"]:
        finding = checker.check(_meds(f"{primary_agent} dose", "fluconazole dose"))[0]
        assert finding.agent == primary_agent
    for partner_agent in ["fluconazole", "diflucan"]:
        finding = checker.check(_meds("phenytoin dose", f"{partner_agent} dose"))[0]
        assert finding.partner_agent == partner_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = PhenytoinFluconazoleChecker()
    assert checker.check(_meds("phenytoinlike", "fluconazolelike")) == []
    assert len(checker.check(_meds("phenytoin", "fluconazole"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["fluconazole dose", "phenytoin dose", "diflucan dose"]
    checker = PhenytoinFluconazoleChecker()
    forward = checker.check(_meds(*names))
    reverse = checker.check(_meds(*reversed(names)))
    assert [(i.agent, i.partner_agent) for i in forward] == [
        (i.agent, i.partner_agent) for i in reverse
    ]
    assert (
        len(
            checker.check(
                _meds(
                    "phenytoin a",
                    "phenytoin b",
                    "fluconazole a",
                    "fluconazole b",
                )
            )
        )
        == 1
    )


def test_export_alias_matches() -> None:
    assert ExportedChecker is PhenytoinFluconazoleChecker


def test_rationale_mentions_research_only() -> None:
    finding = PhenytoinFluconazoleChecker().check(_meds("phenytoin", "fluconazole"))[0]
    assert finding.rationale.startswith("RESEARCH USE ONLY")


def test_severity_ordering_stable() -> None:
    findings = PhenytoinFluconazoleChecker().check(_meds("phenytoin", "fluconazole"))
    assert findings
    ranks = {Severity.HIGH: 3, Severity.CRITICAL: 4}
    assert ranks[findings[0].severity] >= 3
