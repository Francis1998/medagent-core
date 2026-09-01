"""Tests for the Tamoxifen + Strong CYP2D6 Inhibitor safety checker."""

from medagent.models import Medication, Severity, TamoxifenCyp2d6Risk
from medagent.safety import TamoxifenCyp2d6Checker as ExportedChecker
from medagent.safety.tamoxifen_cyp2d6_checker import TamoxifenCyp2d6Checker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = TamoxifenCyp2d6Checker()
    assert checker.check(_meds("tamoxifen dose")) == []
    assert checker.check(_meds("fluoxetine dose")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = TamoxifenCyp2d6Checker().check(_meds("tamoxifen dose", "fluoxetine dose"))[0]
    assert isinstance(finding, TamoxifenCyp2d6Risk)
    assert finding.agent == "tamoxifen"
    assert finding.partner_agent == "fluoxetine"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["tamoxifen", "nolvadex", "soltamox"]:
        finding = TamoxifenCyp2d6Checker().check(_meds(f"{primary_agent} dose", "fluoxetine dose"))[
            0
        ]
        assert finding.agent == primary_agent
    for partner_agent in [
        "fluoxetine",
        "prozac",
        "paroxetine",
        "paxil",
        "bupropion",
        "wellbutrin",
        "quinidine",
    ]:
        finding = TamoxifenCyp2d6Checker().check(_meds("tamoxifen dose", f"{partner_agent} dose"))[
            0
        ]
        assert finding.partner_agent == partner_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = TamoxifenCyp2d6Checker()
    assert checker.check(_meds("tamoxifenlike", "fluoxetinelike")) == []
    assert len(checker.check(_meds("tamoxifen", "fluoxetine"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["fluoxetine dose", "tamoxifen dose"]
    if (
        len(["fluoxetine", "prozac", "paroxetine", "paxil", "bupropion", "wellbutrin", "quinidine"])
        > 1
    ):
        names.append("prozac dose")
    forward = TamoxifenCyp2d6Checker().check(_meds(*names))
    reverse = TamoxifenCyp2d6Checker().check(_meds(*reversed(names)))
    assert [(i.agent, i.partner_agent) for i in forward] == [
        (i.agent, i.partner_agent) for i in reverse
    ]
    assert (
        len(
            TamoxifenCyp2d6Checker().check(
                _meds("tamoxifen a", "tamoxifen b", "fluoxetine a", "fluoxetine b")
            )
        )
        == 1
    )


def test_export_alias_matches() -> None:
    assert ExportedChecker is TamoxifenCyp2d6Checker


def test_rationale_mentions_research_only() -> None:
    finding = TamoxifenCyp2d6Checker().check(_meds("tamoxifen", "fluoxetine"))[0]
    assert finding.rationale.startswith("RESEARCH USE ONLY")


def test_severity_ordering_stable() -> None:
    findings = TamoxifenCyp2d6Checker().check(_meds("tamoxifen", "fluoxetine"))
    assert findings
    ranks = {Severity.HIGH: 3, Severity.CRITICAL: 4}
    assert ranks[findings[0].severity] >= 3
