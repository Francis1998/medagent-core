"""Tests for the dabigatran P-gp safety checker."""

from medagent.models import DabigatranPgpRisk, Medication, Severity
from medagent.safety import DabigatranPgpChecker as ExportedChecker
from medagent.safety.dabigatran_pgp_checker import DabigatranPgpChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = DabigatranPgpChecker()
    assert checker.check(_meds("Dabigatran dose")) == []
    assert checker.check(_meds("Dronedarone dose")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = DabigatranPgpChecker().check(_meds("Dabigatran dose", "Dronedarone dose"))[0]
    assert isinstance(finding, DabigatranPgpRisk)
    assert finding.agent == "dabigatran"
    assert finding.partner_agent == "dronedarone"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "bleeding" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["dabigatran", "pradaxa"]:
        finding = DabigatranPgpChecker().check(_meds(f"{primary_agent} dose", "Dronedarone dose"))[
            0
        ]
        assert finding.agent == primary_agent
    for partner_agent in [
        "dronedarone",
        "ketoconazole",
        "itraconazole",
        "cyclosporine",
        "ciclosporin",
    ]:
        finding = DabigatranPgpChecker().check(_meds("Dabigatran dose", f"{partner_agent} dose"))[0]
        assert finding.partner_agent == partner_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = DabigatranPgpChecker()
    assert checker.check(_meds("dabigatranlike", "dronedaronefrees")) == []
    assert len(checker.check(_meds("Dabigatran", "Dronedarone"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Dronedarone dose", "Dabigatran dose", "Ketoconazole dose"]
    forward = DabigatranPgpChecker().check(_meds(*names))
    reverse = DabigatranPgpChecker().check(_meds(*reversed(names)))
    assert [(i.agent, i.partner_agent) for i in forward] == [
        (i.agent, i.partner_agent) for i in reverse
    ]
    assert (
        len(
            DabigatranPgpChecker().check(
                _meds("Dabigatran a", "Dabigatran b", "Dronedarone a", "Dronedarone b")
            )
        )
        == 1
    )


def test_findings_sorted_deterministically_by_partner() -> None:
    findings = DabigatranPgpChecker().check(
        _meds("Dabigatran dose", "Ketoconazole dose", "Dronedarone dose")
    )
    assert [f.partner_agent for f in findings] == sorted(f.partner_agent for f in findings)


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        DabigatranPgpChecker().check(_meds("dabigatran and dronedarone interaction warning")) == []
    )
    finding = ExportedChecker().check(_meds("Pradaxa dose", "Dronedarone dose"))[0]
    assert finding.agent == "pradaxa"
    assert finding.partner_agent == "dronedarone"
