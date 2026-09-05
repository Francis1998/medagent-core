"""Tests for the Sirolimus + Strong CYP3A4 Inhibitor Risk safety checker."""

from medagent.models import Medication, Severity, SirolimusStrongCyp3a4Risk
from medagent.safety import SirolimusStrongCyp3a4Checker as ExportedChecker
from medagent.safety.sirolimus_strong_cyp3a4_checker import SirolimusStrongCyp3a4Checker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = SirolimusStrongCyp3a4Checker()
    assert checker.check(_meds("sirolimus dose")) == []
    assert checker.check(_meds("ketoconazole dose")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    checker = SirolimusStrongCyp3a4Checker()
    finding = checker.check(_meds("sirolimus dose", "ketoconazole dose"))[0]
    assert isinstance(finding, SirolimusStrongCyp3a4Risk)
    assert finding.agent == "sirolimus"
    assert finding.partner_agent == "ketoconazole"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale


def test_all_supported_agents_participate() -> None:
    checker = SirolimusStrongCyp3a4Checker()
    for primary_agent in ["sirolimus", "rapamune"]:
        finding = checker.check(_meds(f"{primary_agent} dose", "ketoconazole dose"))[0]
        assert finding.agent == primary_agent
    for partner_agent in [
        "ketoconazole",
        "clarithromycin",
        "itraconazole",
        "ritonavir",
        "grapefruit",
    ]:
        finding = checker.check(_meds("sirolimus dose", f"{partner_agent} dose"))[0]
        assert finding.partner_agent == partner_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = SirolimusStrongCyp3a4Checker()
    assert checker.check(_meds("sirolimuslike", "ketoconazolelike")) == []
    assert len(checker.check(_meds("sirolimus", "ketoconazole"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["ketoconazole dose", "sirolimus dose"]
    if len(["sirolimus", "rapamune"]) > 1:
        names.append("rapamune dose")
    checker = SirolimusStrongCyp3a4Checker()
    forward = checker.check(_meds(*names))
    reverse = checker.check(_meds(*reversed(names)))
    assert [(i.agent, i.partner_agent) for i in forward] == [
        (i.agent, i.partner_agent) for i in reverse
    ]
    assert (
        len(
            checker.check(
                _meds(
                    "sirolimus a",
                    "sirolimus b",
                    "ketoconazole a",
                    "ketoconazole b",
                )
            )
        )
        == 1
    )


def test_export_alias_matches() -> None:
    assert ExportedChecker is SirolimusStrongCyp3a4Checker


def test_rationale_mentions_research_only() -> None:
    finding = SirolimusStrongCyp3a4Checker().check(_meds("sirolimus", "ketoconazole"))[0]
    assert finding.rationale.startswith("RESEARCH USE ONLY")


def test_severity_ordering_stable() -> None:
    findings = SirolimusStrongCyp3a4Checker().check(_meds("sirolimus", "ketoconazole"))
    assert findings
    ranks = {Severity.HIGH: 3, Severity.CRITICAL: 4, Severity.MODERATE: 2}
    assert ranks[findings[0].severity] >= 2
