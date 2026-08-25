"""Tests for the fentanyl + CYP3A4 inhibitor exposure checker."""

from medagent.models import FentanylCyp3a4Risk, Medication, Severity
from medagent.safety import FentanylCyp3a4Checker as ExportedChecker
from medagent.safety.fentanyl_cyp3a4_checker import FentanylCyp3a4Checker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = FentanylCyp3a4Checker()
    assert checker.check(_meds("Fentanyl patch 25 mcg")) == []
    assert checker.check(_meds("Ketoconazole 200 mg")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = FentanylCyp3a4Checker().check(_meds("Fentanyl patch", "Ketoconazole 200 mg"))[0]

    assert isinstance(finding, FentanylCyp3a4Risk)
    assert finding.agent == "fentanyl"
    assert finding.partner_agent == "ketoconazole"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "respiratory" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["fentanyl", "duragesic", "abstral", "fentora", "actiq"]:
        finding = FentanylCyp3a4Checker().check(
            _meds(f"{primary_agent} dose", "Ketoconazole 200 mg")
        )[0]
        assert finding.agent == primary_agent

    for partner_agent, label, severity in [
        ("ketoconazole", "Ketoconazole 200 mg", Severity.CRITICAL),
        ("itraconazole", "Itraconazole 200 mg", Severity.CRITICAL),
        ("ritonavir", "Ritonavir 100 mg", Severity.CRITICAL),
        ("clarithromycin", "Clarithromycin 500 mg", Severity.CRITICAL),
        ("nefazodone", "Nefazodone 100 mg", Severity.CRITICAL),
        ("erythromycin", "Erythromycin 250 mg", Severity.HIGH),
        ("fluconazole", "Fluconazole 200 mg", Severity.HIGH),
        ("diltiazem", "Diltiazem 120 mg", Severity.HIGH),
        ("verapamil", "Verapamil 80 mg", Severity.HIGH),
    ]:
        finding = FentanylCyp3a4Checker().check(_meds("Fentanyl patch", label))[0]
        assert finding.partner_agent == partner_agent
        assert finding.severity is severity


def test_related_but_out_of_scope_agents_do_not_flag() -> None:
    checker = FentanylCyp3a4Checker()
    # Distinct from opioid+benzo and general opioid checkers; weak/out-of-panel CYP inhibitors
    for agent in ["Alprazolam", "Morphine", "Cimetidine", "Grapefruit"]:
        assert checker.check(_meds("Fentanyl patch", agent)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = FentanylCyp3a4Checker()
    assert checker.check(_meds("Fentanyllike", "Ketoconazolefree")) == []
    assert len(checker.check(_meds("Duragesic", "Ritonavir"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Ketoconazole 200 mg", "Fentanyl patch", "Verapamil 80 mg"]
    forward = FentanylCyp3a4Checker().check(_meds(*names))
    reverse = FentanylCyp3a4Checker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert (
        len(
            FentanylCyp3a4Checker().check(
                _meds(
                    "Fentanyl patch",
                    "Fentanyl patch",
                    "Ketoconazole 200 mg",
                    "Ketoconazole 200 mg",
                )
            )
        )
        == 1
    )


def test_findings_sorted_by_severity_first() -> None:
    findings = FentanylCyp3a4Checker().check(
        _meds("Fentanyl patch", "Verapamil 80 mg", "Ketoconazole 200 mg")
    )
    assert [finding.severity for finding in findings] == [Severity.CRITICAL, Severity.HIGH]
    assert findings[0].partner_agent == "ketoconazole"
    assert findings[1].partner_agent == "verapamil"


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        FentanylCyp3a4Checker().check(_meds("Fentanyl and ketoconazole interaction warning")) == []
    )
    finding = ExportedChecker().check(_meds("Actiq", "Fluconazole"))[0]
    assert finding.severity is Severity.HIGH
