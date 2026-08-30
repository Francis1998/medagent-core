"""Tests for the midazolam CYP3A4 safety checker."""

from medagent.models import Medication, MidazolamCyp3a4Risk, Severity
from medagent.safety import MidazolamCyp3a4Checker as ExportedChecker
from medagent.safety.midazolam_cyp3a4_checker import MidazolamCyp3a4Checker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = MidazolamCyp3a4Checker()
    assert checker.check(_meds("Midazolam dose")) == []
    assert checker.check(_meds("Ketoconazole dose")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = MidazolamCyp3a4Checker().check(_meds("Midazolam dose", "Ketoconazole dose"))[0]
    assert isinstance(finding, MidazolamCyp3a4Risk)
    assert finding.agent == "midazolam"
    assert finding.partner_agent == "ketoconazole"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "sedation" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["midazolam", "versed"]:
        finding = MidazolamCyp3a4Checker().check(
            _meds(f"{primary_agent} dose", "Ketoconazole dose")
        )[0]
        assert finding.agent == primary_agent
    for partner_agent in [
        "ketoconazole",
        "clarithromycin",
        "ritonavir",
        "itraconazole",
        "nefazodone",
    ]:
        finding = MidazolamCyp3a4Checker().check(_meds("Midazolam dose", f"{partner_agent} dose"))[
            0
        ]
        assert finding.partner_agent == partner_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = MidazolamCyp3a4Checker()
    assert checker.check(_meds("midazolamlike", "ketoconazolefrees")) == []
    assert len(checker.check(_meds("Midazolam", "Ketoconazole"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Ketoconazole dose", "Midazolam dose", "Clarithromycin dose"]
    forward = MidazolamCyp3a4Checker().check(_meds(*names))
    reverse = MidazolamCyp3a4Checker().check(_meds(*reversed(names)))
    assert [(i.agent, i.partner_agent) for i in forward] == [
        (i.agent, i.partner_agent) for i in reverse
    ]
    assert (
        len(
            MidazolamCyp3a4Checker().check(
                _meds("Midazolam a", "Midazolam b", "Ketoconazole a", "Ketoconazole b")
            )
        )
        == 1
    )


def test_findings_sorted_deterministically_by_partner() -> None:
    findings = MidazolamCyp3a4Checker().check(
        _meds("Midazolam dose", "Clarithromycin dose", "Ketoconazole dose")
    )
    assert [f.partner_agent for f in findings] == sorted(f.partner_agent for f in findings)


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        MidazolamCyp3a4Checker().check(_meds("midazolam and ketoconazole interaction warning"))
        == []
    )
    finding = ExportedChecker().check(_meds("Versed dose", "Ketoconazole dose"))[0]
    assert finding.agent == "versed"
    assert finding.partner_agent == "ketoconazole"
