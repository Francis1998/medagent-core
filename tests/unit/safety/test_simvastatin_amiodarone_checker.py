"""Tests for the simvastatin + amiodarone safety checker."""

from medagent.models import Medication, Severity, SimvastatinAmiodaroneRisk
from medagent.safety import SimvastatinAmiodaroneChecker as ExportedChecker
from medagent.safety.simvastatin_amiodarone_checker import SimvastatinAmiodaroneChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = SimvastatinAmiodaroneChecker()
    assert checker.check(_meds("Simvastatin dose")) == []
    assert checker.check(_meds("Amiodarone dose")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = SimvastatinAmiodaroneChecker().check(
        _meds("Simvastatin dose", "Amiodarone dose")
    )[0]
    assert isinstance(finding, SimvastatinAmiodaroneRisk)
    assert finding.agent == "simvastatin"
    assert finding.partner_agent == "amiodarone"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "myopathy" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["simvastatin", "zocor"]:
        finding = SimvastatinAmiodaroneChecker().check(
            _meds(f"{primary_agent} dose", "Amiodarone dose")
        )[0]
        assert finding.agent == primary_agent
    for partner_agent in ["amiodarone", "cordarone"]:
        finding = SimvastatinAmiodaroneChecker().check(
            _meds("Simvastatin dose", f"{partner_agent} dose")
        )[0]
        assert finding.partner_agent == partner_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = SimvastatinAmiodaroneChecker()
    assert checker.check(_meds("simvastatinlike", "amiodaronelike")) == []
    assert len(checker.check(_meds("Simvastatin", "Amiodarone"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Amiodarone dose", "Simvastatin dose", "Cordarone dose"]
    forward = SimvastatinAmiodaroneChecker().check(_meds(*names))
    reverse = SimvastatinAmiodaroneChecker().check(_meds(*reversed(names)))
    assert [(i.agent, i.partner_agent) for i in forward] == [
        (i.agent, i.partner_agent) for i in reverse
    ]
    assert (
        len(
            SimvastatinAmiodaroneChecker().check(
                _meds("Simvastatin a", "Simvastatin b", "Amiodarone a", "Amiodarone b")
            )
        )
        == 1
    )


def test_findings_sorted_deterministically_by_partner() -> None:
    findings = SimvastatinAmiodaroneChecker().check(
        _meds("Simvastatin dose", "Cordarone dose", "Amiodarone dose")
    )
    assert [f.partner_agent for f in findings] == sorted(f.partner_agent for f in findings)


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        SimvastatinAmiodaroneChecker().check(
            _meds("simvastatin and amiodarone interaction warning")
        )
        == []
    )
    finding = ExportedChecker().check(_meds("Zocor dose", "Cordarone dose"))[0]
    assert finding.agent == "zocor"
    assert finding.partner_agent == "cordarone"
