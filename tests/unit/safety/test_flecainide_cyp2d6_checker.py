"""Tests for the Flecainide + Strong CYP2D6 Inhibitor Risk safety checker."""

from medagent.models import FlecainideCyp2d6Risk, Medication, Severity
from medagent.safety import FlecainideCyp2d6Checker as ExportedChecker
from medagent.safety.flecainide_cyp2d6_checker import FlecainideCyp2d6Checker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = FlecainideCyp2d6Checker()
    assert checker.check(_meds("flecainide dose")) == []
    assert checker.check(_meds("fluoxetine dose")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    checker = FlecainideCyp2d6Checker()
    finding = checker.check(_meds("flecainide dose", "fluoxetine dose"))[0]
    assert isinstance(finding, FlecainideCyp2d6Risk)
    assert finding.agent == "flecainide"
    assert finding.partner_agent == "fluoxetine"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale


def test_all_supported_agents_participate() -> None:
    checker = FlecainideCyp2d6Checker()
    for primary_agent in ["flecainide", "tambocor"]:
        finding = checker.check(_meds(f"{primary_agent} dose", "fluoxetine dose"))[0]
        assert finding.agent == primary_agent
    for partner_agent in ["fluoxetine", "paroxetine", "bupropion", "quinidine", "prozac", "paxil"]:
        finding = checker.check(_meds("flecainide dose", f"{partner_agent} dose"))[0]
        assert finding.partner_agent == partner_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = FlecainideCyp2d6Checker()
    assert checker.check(_meds("flecainidelike", "fluoxetinelike")) == []
    assert len(checker.check(_meds("flecainide", "fluoxetine"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["fluoxetine dose", "flecainide dose"]
    if len(["flecainide", "tambocor"]) > 1:
        names.append("tambocor dose")
    checker = FlecainideCyp2d6Checker()
    forward = checker.check(_meds(*names))
    reverse = checker.check(_meds(*reversed(names)))
    assert [(i.agent, i.partner_agent) for i in forward] == [
        (i.agent, i.partner_agent) for i in reverse
    ]
    assert (
        len(
            checker.check(
                _meds(
                    "flecainide a",
                    "flecainide b",
                    "fluoxetine a",
                    "fluoxetine b",
                )
            )
        )
        == 1
    )


def test_export_alias_matches() -> None:
    assert ExportedChecker is FlecainideCyp2d6Checker


def test_rationale_mentions_research_only() -> None:
    finding = FlecainideCyp2d6Checker().check(_meds("flecainide", "fluoxetine"))[0]
    assert finding.rationale.startswith("RESEARCH USE ONLY")


def test_severity_ordering_stable() -> None:
    findings = FlecainideCyp2d6Checker().check(_meds("flecainide", "fluoxetine"))
    assert findings
    ranks = {Severity.HIGH: 3, Severity.CRITICAL: 4}
    assert ranks[findings[0].severity] >= 3
