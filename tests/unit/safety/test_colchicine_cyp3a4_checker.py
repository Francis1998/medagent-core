"""Tests for the colchicine + strong CYP3A4/P-gp inhibitor checker."""

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


def test_flags_supported_pair_at_critical_severity() -> None:
    finding = ColchicineCyp3a4Checker().check(
        _meds("Colchicine 0.6 mg daily", "Clarithromycin 500 mg BID")
    )[0]

    assert isinstance(finding, ColchicineCyp3a4Risk)
    assert finding.agent == "colchicine"
    assert finding.partner_agent == "clarithromycin"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "boxed-warning" in finding.rationale.lower() or "fatal" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["colchicine", "colcrys", "mitigare", "gloperba"]:
        finding = ColchicineCyp3a4Checker().check(
            _meds(f"{primary_agent} dose", "Clarithromycin 500 mg")
        )[0]
        assert finding.agent == primary_agent

    for partner_agent in [
        "clarithromycin",
        "ketoconazole",
        "itraconazole",
        "ritonavir",
        "cyclosporine",
        "ciclosporin",
        "cobicistat",
        "posaconazole",
    ]:
        finding = ColchicineCyp3a4Checker().check(
            _meds("Colchicine 0.6 mg", f"{partner_agent} 200 mg")
        )[0]
        assert finding.partner_agent == partner_agent
        assert finding.severity is Severity.CRITICAL


def test_related_but_out_of_scope_agents_do_not_flag() -> None:
    checker = ColchicineCyp3a4Checker()
    # Distinct from fentanyl CYP3A4; moderate/weak inhibitors remain out of panel
    for agent in ["Azithromycin", "Fluconazole", "Fentanyl", "Grapefruit"]:
        assert checker.check(_meds("Colchicine 0.6 mg", agent)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = ColchicineCyp3a4Checker()
    assert checker.check(_meds("Colchicinelike", "Ritonavirfree")) == []
    assert len(checker.check(_meds("Colchicine", "Ritonavir"))) == 1
    assert len(checker.check(_meds("Colchicine", "Cyclosporine"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Ritonavir 100 mg", "Colchicine 0.6 mg", "Cyclosporine 100 mg"]
    forward = ColchicineCyp3a4Checker().check(_meds(*names))
    reverse = ColchicineCyp3a4Checker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
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


def test_findings_sorted_deterministically() -> None:
    findings = ColchicineCyp3a4Checker().check(
        _meds("Colchicine 0.6 mg", "Ritonavir 100 mg", "Cyclosporine 100 mg")
    )
    assert [finding.severity for finding in findings] == [Severity.CRITICAL, Severity.CRITICAL]
    assert [finding.partner_agent for finding in findings] == ["cyclosporine", "ritonavir"]


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        ColchicineCyp3a4Checker().check(_meds("Colchicine and ritonavir interaction warning")) == []
    )
    finding = ExportedChecker().check(_meds("Colcrys 0.6 mg", "Ketoconazole 200 mg"))[0]
    assert finding.agent == "colcrys"
    assert finding.partner_agent == "ketoconazole"
    assert finding.severity is Severity.CRITICAL
