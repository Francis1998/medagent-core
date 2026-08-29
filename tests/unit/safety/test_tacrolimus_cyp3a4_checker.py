"""Tests for the tacrolimus CYP3A4 safety checker."""

from medagent.models import Medication, Severity, TacrolimusCyp3a4Risk
from medagent.safety import TacrolimusCyp3a4Checker as ExportedChecker
from medagent.safety.tacrolimus_cyp3a4_checker import TacrolimusCyp3a4Checker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = TacrolimusCyp3a4Checker()
    assert checker.check(_meds("Tacrolimus dose")) == []
    assert checker.check(_meds("Ketoconazole dose")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = TacrolimusCyp3a4Checker().check(_meds("Tacrolimus dose", "Ketoconazole dose"))[0]

    assert isinstance(finding, TacrolimusCyp3a4Risk)
    assert finding.agent == "tacrolimus"
    assert finding.partner_agent == "ketoconazole"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "nephrotoxicity" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["tacrolimus", "prograf", "envarsus", "astagraf"]:
        finding = TacrolimusCyp3a4Checker().check(
            _meds(f"{primary_agent} dose", "Ketoconazole dose")
        )[0]
        assert finding.agent == primary_agent

    for partner_agent in [
        "ketoconazole",
        "itraconazole",
        "clarithromycin",
        "ritonavir",
        "cobicistat",
    ]:
        finding = TacrolimusCyp3a4Checker().check(
            _meds("Tacrolimus dose", f"{partner_agent} dose")
        )[0]
        assert finding.partner_agent == partner_agent
        assert finding.severity is Severity.CRITICAL


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = TacrolimusCyp3a4Checker()
    assert checker.check(_meds("tacrolimuslike", "ketoconazolefrees")) == []
    assert len(checker.check(_meds("Tacrolimus", "Ketoconazole"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Ketoconazole dose", "Tacrolimus dose", "Itraconazole dose"]
    forward = TacrolimusCyp3a4Checker().check(_meds(*names))
    reverse = TacrolimusCyp3a4Checker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent) for item in forward] == [
        (item.agent, item.partner_agent) for item in reverse
    ]
    assert (
        len(
            TacrolimusCyp3a4Checker().check(
                _meds(
                    "Tacrolimus a",
                    "Tacrolimus b",
                    "Ketoconazole a",
                    "Ketoconazole b",
                )
            )
        )
        == 1
    )


def test_findings_sorted_deterministically_by_partner() -> None:
    findings = TacrolimusCyp3a4Checker().check(
        _meds("Tacrolimus dose", "Itraconazole dose", "Ketoconazole dose")
    )
    assert all(finding.severity is Severity.CRITICAL for finding in findings)
    assert [finding.partner_agent for finding in findings] == sorted(
        [finding.partner_agent for finding in findings]
    )


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        TacrolimusCyp3a4Checker().check(_meds("tacrolimus and ketoconazole interaction warning"))
        == []
    )
    finding = ExportedChecker().check(_meds("Prograf dose", "Ketoconazole dose"))[0]
    assert finding.agent == "prograf"
    assert finding.partner_agent == "ketoconazole"
    assert finding.severity is Severity.CRITICAL
