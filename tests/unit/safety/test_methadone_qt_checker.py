"""Tests for the methadone + QT-prolonging drug intensification checker."""

from medagent.models import Medication, MethadoneQtRisk, Severity
from medagent.safety import MethadoneQtChecker as ExportedChecker
from medagent.safety.methadone_qt_checker import MethadoneQtChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = MethadoneQtChecker()
    assert checker.check(_meds("Methadone 10 mg")) == []
    assert checker.check(_meds("Haloperidol 5 mg")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = MethadoneQtChecker().check(_meds("Methadone 10 mg", "Haloperidol 5 mg"))[0]

    assert isinstance(finding, MethadoneQtRisk)
    assert finding.agent == "methadone"
    assert finding.partner_agent == "haloperidol"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "torsades" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["methadone", "dolophine", "methadose"]:
        finding = MethadoneQtChecker().check(_meds(f"{primary_agent} dose", "Azithromycin 250 mg"))[
            0
        ]
        assert finding.agent == primary_agent

    for partner_agent, label, severity in [
        ("haloperidol", "Haloperidol 5 mg", Severity.CRITICAL),
        ("ziprasidone", "Ziprasidone 40 mg", Severity.CRITICAL),
        ("citalopram", "Citalopram 20 mg", Severity.CRITICAL),
        ("ondansetron", "Ondansetron 4 mg", Severity.HIGH),
        ("azithromycin", "Azithromycin 250 mg", Severity.HIGH),
        ("escitalopram", "Escitalopram 10 mg", Severity.HIGH),
    ]:
        finding = MethadoneQtChecker().check(_meds("Methadone 10 mg", label))[0]
        assert finding.partner_agent == partner_agent
        assert finding.severity is severity


def test_related_but_out_of_scope_agents_do_not_flag() -> None:
    checker = MethadoneQtChecker()
    # Distinct from the general multi-drug QT screen (qt_prolongation_checker.py)
    for agent in ["Amiodarone", "Sotalol", "Fluoxetine", "Ciprofloxacin"]:
        assert checker.check(_meds("Methadone 10 mg", agent)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = MethadoneQtChecker()
    assert checker.check(_meds("Methadonelike", "Haloperidolfree")) == []
    assert len(checker.check(_meds("Dolophine", "Ziprasidone"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Haloperidol 5 mg", "Methadone 10 mg", "Citalopram 20 mg"]
    forward = MethadoneQtChecker().check(_meds(*names))
    reverse = MethadoneQtChecker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert (
        len(
            MethadoneQtChecker().check(
                _meds(
                    "Methadone 10 mg",
                    "Methadone 10 mg",
                    "Haloperidol 5 mg",
                    "Haloperidol 5 mg",
                )
            )
        )
        == 1
    )


def test_findings_sorted_by_severity_first() -> None:
    findings = MethadoneQtChecker().check(
        _meds("Methadone 10 mg", "Ondansetron 4 mg", "Haloperidol 5 mg")
    )
    assert [finding.severity for finding in findings] == [Severity.CRITICAL, Severity.HIGH]
    assert findings[0].partner_agent == "haloperidol"
    assert findings[1].partner_agent == "ondansetron"


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert MethadoneQtChecker().check(_meds("Methadone and haloperidol interaction warning")) == []
    finding = ExportedChecker().check(_meds("Methadose", "Escitalopram"))[0]
    assert finding.severity is Severity.HIGH
