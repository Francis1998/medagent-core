"""Tests for the colchicine + strong CYP3A4 inhibitor checker."""

from medagent.models import ColchicineCyp3a4Risk, Medication, Severity
from medagent.safety import ColchicineCyp3a4Checker as ExportedChecker
from medagent.safety.colchicine_cyp3a4_checker import ColchicineCyp3a4Checker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = ColchicineCyp3a4Checker()
    assert checker.check(_meds("Colchicine 0.6 mg daily")) == []
    assert checker.check(_meds("Clarithromycin 500 mg BID")) == []
    assert checker.check([]) == []


def test_flags_colchicine_plus_clarithromycin_critical() -> None:
    finding = ColchicineCyp3a4Checker().check(
        _meds("Colchicine 0.6 mg daily", "Clarithromycin 500 mg BID")
    )[0]

    assert isinstance(finding, ColchicineCyp3a4Risk)
    assert finding.agent == "colchicine"
    assert finding.partner_agent == "clarithromycin"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "CYP3A4" in finding.rationale
    assert "fatal" in finding.rationale


def test_all_supported_agents_participate_as_critical() -> None:
    for colchicine_agent in ["colchicine", "colcrys", "mitigare", "gloperba"]:
        finding = ColchicineCyp3a4Checker().check(
            _meds(
                f"{colchicine_agent.title()} 0.6 mg",
                "Clarithromycin 500 mg",
            )
        )[0]
        assert finding.agent == colchicine_agent

    for inhibitor in [
        "clarithromycin",
        "ketoconazole",
        "itraconazole",
        "ritonavir",
    ]:
        finding = ColchicineCyp3a4Checker().check(
            _meds("Colchicine 0.6 mg", f"{inhibitor.title()} 200 mg")
        )[0]
        assert finding.partner_agent == inhibitor
        assert finding.severity is Severity.CRITICAL


def test_non_panel_inhibitors_are_out_of_scope() -> None:
    checker = ColchicineCyp3a4Checker()
    for partner in ["Azithromycin", "Fluconazole", "Grapefruit juice"]:
        assert checker.check(_meds("Colchicine 0.6 mg", partner)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = ColchicineCyp3a4Checker()
    assert checker.check(_meds("Colchicinelike", "Ritonavirfree")) == []
    assert len(checker.check(_meds("Colchicine", "Ritonavir"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = [
        "Ritonavir 100 mg",
        "Colchicine 0.6 mg",
        "Itraconazole 200 mg",
    ]
    forward = ColchicineCyp3a4Checker().check(_meds(*names))
    reverse = ColchicineCyp3a4Checker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert [item.partner_agent for item in forward] == [
        "itraconazole",
        "ritonavir",
    ]
    assert (
        len(
            ColchicineCyp3a4Checker().check(
                _meds(
                    "Colchicine 0.6 mg",
                    "Colchicine 0.3 mg",
                    "Ritonavir 100 mg",
                    "Ritonavir 50 mg",
                )
            )
        )
        == 1
    )


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        ColchicineCyp3a4Checker().check(_meds("Colchicine and ritonavir interaction warning")) == []
    )
    finding = ExportedChecker().check(_meds("Colcrys 0.6 mg", "Ketoconazole 200 mg"))[0]
    assert finding.agent == "colcrys"
    assert finding.partner_agent == "ketoconazole"
