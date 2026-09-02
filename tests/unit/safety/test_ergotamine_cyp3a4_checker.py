"""Tests for the Ergotamine + Strong CYP3A4 safety checker."""

from medagent.models import ErgotamineCyp3a4Risk, Medication, Severity
from medagent.safety import ErgotamineCyp3a4Checker as ExportedChecker
from medagent.safety.ergotamine_cyp3a4_checker import (
    ErgotamineCyp3a4Checker,
)


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = ErgotamineCyp3a4Checker()
    assert checker.check(_meds("ergotamine dose")) == []
    assert checker.check(_meds("clarithromycin dose")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    checker = ErgotamineCyp3a4Checker()
    finding = checker.check(_meds("ergotamine dose", "clarithromycin dose"))[0]
    assert isinstance(finding, ErgotamineCyp3a4Risk)
    assert finding.agent == "ergotamine"
    assert finding.partner_agent == "clarithromycin"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale


def test_all_supported_agents_participate() -> None:
    checker = ErgotamineCyp3a4Checker()
    for primary_agent in ["ergotamine", "cafergot", "dihydroergotamine", "migranal", "dhe-45"]:
        finding = checker.check(_meds(f"{primary_agent} dose", "clarithromycin dose"))[0]
        assert finding.agent == primary_agent
    for partner_agent in [
        "clarithromycin",
        "ketoconazole",
        "itraconazole",
        "ritonavir",
        "cobicistat",
    ]:
        finding = checker.check(_meds("ergotamine dose", f"{partner_agent} dose"))[0]
        assert finding.partner_agent == partner_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = ErgotamineCyp3a4Checker()
    assert checker.check(_meds("ergotaminelike", "clarithromycinlike")) == []
    assert len(checker.check(_meds("ergotamine", "clarithromycin"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["clarithromycin dose", "ergotamine dose", "ketoconazole dose"]
    checker = ErgotamineCyp3a4Checker()
    forward = checker.check(_meds(*names))
    reverse = checker.check(_meds(*reversed(names)))
    assert [(i.agent, i.partner_agent) for i in forward] == [
        (i.agent, i.partner_agent) for i in reverse
    ]
    assert (
        len(
            checker.check(
                _meds(
                    "ergotamine a",
                    "ergotamine b",
                    "clarithromycin a",
                    "clarithromycin b",
                )
            )
        )
        == 1
    )


def test_export_alias_matches() -> None:
    assert ExportedChecker is ErgotamineCyp3a4Checker


def test_rationale_mentions_research_only() -> None:
    finding = ErgotamineCyp3a4Checker().check(_meds("ergotamine", "clarithromycin"))[0]
    assert finding.rationale.startswith("RESEARCH USE ONLY")


def test_severity_ordering_stable() -> None:
    findings = ErgotamineCyp3a4Checker().check(_meds("ergotamine", "clarithromycin"))
    assert findings
    ranks = {Severity.HIGH: 3, Severity.CRITICAL: 4}
    assert ranks[findings[0].severity] >= 3
