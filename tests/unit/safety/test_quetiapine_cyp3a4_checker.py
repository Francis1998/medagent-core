"""Tests for the quetiapine + strong CYP3A4 inhibitor checker."""

from medagent.models import Medication, QuetiapineCyp3a4Risk, Severity
from medagent.safety import QuetiapineCyp3a4Checker as ExportedChecker
from medagent.safety.quetiapine_cyp3a4_checker import QuetiapineCyp3a4Checker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = QuetiapineCyp3a4Checker()
    assert checker.check(_meds("Quetiapine 200 mg BID")) == []
    assert checker.check(_meds("Ketoconazole 200 mg")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = QuetiapineCyp3a4Checker().check(
        _meds("Quetiapine 200 mg BID", "Ketoconazole 200 mg")
    )[0]

    assert isinstance(finding, QuetiapineCyp3a4Risk)
    assert finding.agent == "quetiapine"
    assert finding.partner_agent == "ketoconazole"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "qt" in finding.rationale.lower() or "sedation" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["quetiapine", "seroquel"]:
        finding = QuetiapineCyp3a4Checker().check(
            _meds(f"{primary_agent} dose", "Ketoconazole 200 mg")
        )[0]
        assert finding.agent == primary_agent

    for partner_agent, label, severity in [
        ("ketoconazole", "Ketoconazole 200 mg", Severity.CRITICAL),
        ("itraconazole", "Itraconazole 200 mg", Severity.CRITICAL),
        ("ritonavir", "Ritonavir 100 mg", Severity.CRITICAL),
        ("cobicistat", "Cobicistat 150 mg", Severity.CRITICAL),
        ("clarithromycin", "Clarithromycin 500 mg", Severity.HIGH),
    ]:
        finding = QuetiapineCyp3a4Checker().check(_meds("Quetiapine 200 mg", label))[0]
        assert finding.partner_agent == partner_agent
        assert finding.severity is severity


def test_related_but_out_of_scope_agents_do_not_flag() -> None:
    checker = QuetiapineCyp3a4Checker()
    # Distinct from colchicine_cyp3a4 and fentanyl_cyp3a4
    for agent in ["Colchicine", "Fentanyl", "Fluconazole", "Erythromycin"]:
        assert checker.check(_meds("Quetiapine 200 mg", agent)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = QuetiapineCyp3a4Checker()
    assert checker.check(_meds("Quetiapinelike", "Ketoconazolefree")) == []
    assert len(checker.check(_meds("Quetiapine", "Ketoconazole"))) == 1
    assert len(checker.check(_meds("Seroquel", "Ritonavir"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Clarithromycin 500 mg", "Quetiapine 200 mg", "Ketoconazole 200 mg"]
    forward = QuetiapineCyp3a4Checker().check(_meds(*names))
    reverse = QuetiapineCyp3a4Checker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert (
        len(
            QuetiapineCyp3a4Checker().check(
                _meds(
                    "Quetiapine 200 mg",
                    "Quetiapine 100 mg",
                    "Ketoconazole 200 mg",
                    "Ketoconazole 100 mg",
                )
            )
        )
        == 1
    )


def test_findings_sorted_by_severity_first() -> None:
    findings = QuetiapineCyp3a4Checker().check(
        _meds("Quetiapine 200 mg", "Clarithromycin 500 mg", "Ketoconazole 200 mg")
    )
    assert [finding.severity for finding in findings] == [Severity.CRITICAL, Severity.HIGH]
    assert findings[0].partner_agent == "ketoconazole"
    assert findings[1].partner_agent == "clarithromycin"


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        QuetiapineCyp3a4Checker().check(_meds("Quetiapine and ketoconazole interaction warning"))
        == []
    )
    finding = ExportedChecker().check(_meds("Seroquel 200 mg", "Cobicistat 150 mg"))[0]
    assert finding.agent == "seroquel"
    assert finding.partner_agent == "cobicistat"
    assert finding.severity is Severity.CRITICAL
