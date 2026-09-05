"""Tests for the Tacrolimus + Rifampin Induction Risk safety checker."""

from medagent.models import Medication, Severity, TacrolimusRifampinRisk
from medagent.safety import TacrolimusRifampinChecker as ExportedChecker
from medagent.safety.tacrolimus_rifampin_checker import TacrolimusRifampinChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = TacrolimusRifampinChecker()
    assert checker.check(_meds("tacrolimus dose")) == []
    assert checker.check(_meds("rifampin dose")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    checker = TacrolimusRifampinChecker()
    finding = checker.check(_meds("tacrolimus dose", "rifampin dose"))[0]
    assert isinstance(finding, TacrolimusRifampinRisk)
    assert finding.agent == "tacrolimus"
    assert finding.partner_agent == "rifampin"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale


def test_all_supported_agents_participate() -> None:
    checker = TacrolimusRifampinChecker()
    for primary_agent in ["tacrolimus", "prograf", "envarsus", "astagraf"]:
        finding = checker.check(_meds(f"{primary_agent} dose", "rifampin dose"))[0]
        assert finding.agent == primary_agent
    for partner_agent in ["rifampin", "rifampicin", "rifadin", "rimactane"]:
        finding = checker.check(_meds("tacrolimus dose", f"{partner_agent} dose"))[0]
        assert finding.partner_agent == partner_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = TacrolimusRifampinChecker()
    assert checker.check(_meds("tacrolimuslike", "rifampinlike")) == []
    assert len(checker.check(_meds("tacrolimus", "rifampin"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["rifampin dose", "tacrolimus dose"]
    if len(["tacrolimus", "prograf", "envarsus", "astagraf"]) > 1:
        names.append("prograf dose")
    checker = TacrolimusRifampinChecker()
    forward = checker.check(_meds(*names))
    reverse = checker.check(_meds(*reversed(names)))
    assert [(i.agent, i.partner_agent) for i in forward] == [
        (i.agent, i.partner_agent) for i in reverse
    ]
    assert (
        len(
            checker.check(
                _meds(
                    "tacrolimus a",
                    "tacrolimus b",
                    "rifampin a",
                    "rifampin b",
                )
            )
        )
        == 1
    )


def test_export_alias_matches() -> None:
    assert ExportedChecker is TacrolimusRifampinChecker


def test_rationale_mentions_research_only() -> None:
    finding = TacrolimusRifampinChecker().check(_meds("tacrolimus", "rifampin"))[0]
    assert finding.rationale.startswith("RESEARCH USE ONLY")


def test_severity_ordering_stable() -> None:
    findings = TacrolimusRifampinChecker().check(_meds("tacrolimus", "rifampin"))
    assert findings
    ranks = {Severity.HIGH: 3, Severity.CRITICAL: 4, Severity.MODERATE: 2}
    assert ranks[findings[0].severity] >= 2
