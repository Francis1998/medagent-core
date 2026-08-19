"""Tests for the amiodarone + digoxin P-gp interaction checker."""

from medagent.models import AmiodaroneDigoxinRisk, Medication, Severity
from medagent.safety import AmiodaroneDigoxinChecker as ExportedChecker
from medagent.safety.amiodarone_digoxin_checker import AmiodaroneDigoxinChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = AmiodaroneDigoxinChecker()
    assert checker.check(_meds("Amiodarone 200 mg daily")) == []
    assert checker.check(_meds("Digoxin 0.125 mg daily")) == []
    assert checker.check([]) == []


def test_flags_amiodarone_plus_digoxin_high() -> None:
    finding = AmiodaroneDigoxinChecker().check(
        _meds("Amiodarone 200 mg daily", "Digoxin 0.125 mg daily")
    )[0]

    assert isinstance(finding, AmiodaroneDigoxinRisk)
    assert finding.agent == "amiodarone"
    assert finding.partner_agent == "digoxin"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "P-glycoprotein" in finding.rationale


def test_all_supported_agents_participate() -> None:
    for amiodarone_agent in ["amiodarone", "cordarone", "pacerone"]:
        finding = AmiodaroneDigoxinChecker().check(
            _meds(f"{amiodarone_agent.title()} 200 mg", "Digoxin 0.125 mg")
        )[0]
        assert finding.agent == amiodarone_agent

    for digoxin_agent in ["digoxin", "lanoxin"]:
        finding = AmiodaroneDigoxinChecker().check(
            _meds("Amiodarone 200 mg", f"{digoxin_agent.title()} 0.125 mg")
        )[0]
        assert finding.partner_agent == digoxin_agent
        assert finding.severity is Severity.HIGH


def test_verapamil_control_is_out_of_scope() -> None:
    assert AmiodaroneDigoxinChecker().check(_meds("Verapamil 120 mg", "Digoxin 0.125 mg")) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = AmiodaroneDigoxinChecker()
    assert checker.check(_meds("Amiodaronoid", "Digoxinlike")) == []
    assert len(checker.check(_meds("Amiodarone", "Digoxin"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Lanoxin 0.125 mg", "Pacerone 200 mg", "Amiodarone 100 mg", "Digoxin 0.25 mg"]
    forward = AmiodaroneDigoxinChecker().check(_meds(*names))
    reverse = AmiodaroneDigoxinChecker().check(_meds(*reversed(names)))

    assert [
        (item.medication, item.partner_medication, item.agent, item.partner_agent)
        for item in forward
    ] == [
        (item.medication, item.partner_medication, item.agent, item.partner_agent)
        for item in reverse
    ]
    assert [(item.agent, item.partner_agent) for item in forward] == [
        ("amiodarone", "digoxin"),
        ("amiodarone", "lanoxin"),
        ("pacerone", "digoxin"),
        ("pacerone", "lanoxin"),
    ]
    assert (
        len(
            AmiodaroneDigoxinChecker().check(
                _meds("Amiodarone 200 mg", "Amiodarone 100 mg", "Digoxin", "Digoxin 0.125 mg")
            )
        )
        == 1
    )


def test_single_entry_is_not_coprescription() -> None:
    assert (
        AmiodaroneDigoxinChecker().check(_meds("Amiodarone and digoxin interaction warning")) == []
    )


def test_checker_is_exported_from_safety_package() -> None:
    finding = ExportedChecker().check(_meds("Cordarone 200 mg", "Lanoxin 0.125 mg"))[0]
    assert finding.agent == "cordarone"
    assert finding.partner_agent == "lanoxin"
