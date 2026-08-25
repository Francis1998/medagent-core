"""Tests for the lamotrigine + valproate SJS/TEN risk checker."""

from medagent.models import LamotrigineValproateRisk, Medication, Severity
from medagent.safety import LamotrigineValproateChecker as ExportedChecker
from medagent.safety.lamotrigine_valproate_checker import LamotrigineValproateChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = LamotrigineValproateChecker()
    assert checker.check(_meds("Lamictal 25 mg")) == []
    assert checker.check(_meds("Depakote 500 mg")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = LamotrigineValproateChecker().check(_meds("Lamictal 25 mg", "Depakote 500 mg"))[0]

    assert isinstance(finding, LamotrigineValproateRisk)
    assert finding.agent == "lamictal"
    assert finding.partner_agent == "depakote"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "sjs" in finding.rationale.lower() or "cutaneous" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["lamotrigine", "lamictal"]:
        finding = LamotrigineValproateChecker().check(
            _meds(f"{primary_agent} dose", "Valproate 500 mg")
        )[0]
        assert finding.agent == primary_agent

    for partner_agent, label in [
        ("valproate", "Valproate 500 mg"),
        ("valproic acid", "Valproic acid 250 mg"),
        ("divalproex", "Divalproex 500 mg"),
        ("depakote", "Depakote 500 mg"),
    ]:
        finding = LamotrigineValproateChecker().check(_meds("Lamotrigine 25 mg", label))[0]
        assert finding.partner_agent == partner_agent
        assert finding.severity is Severity.CRITICAL


def test_related_but_out_of_scope_agents_do_not_flag() -> None:
    checker = LamotrigineValproateChecker()
    # Distinct from valproate-carbapenem and other AED partners
    for agent in ["Meropenem", "Carbamazepine", "Levetiracetam", "Phenytoin"]:
        assert checker.check(_meds("Lamotrigine 25 mg", agent)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = LamotrigineValproateChecker()
    assert checker.check(_meds("Lamotriginelike", "Valproatefree")) == []
    assert len(checker.check(_meds("Lamictal", "Depakote"))) == 1
    assert len(checker.check(_meds("Lamotrigine", "Valproic acid"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Depakote 500 mg", "Lamotrigine 25 mg", "Valproate 250 mg"]
    forward = LamotrigineValproateChecker().check(_meds(*names))
    reverse = LamotrigineValproateChecker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert (
        len(
            LamotrigineValproateChecker().check(
                _meds(
                    "Lamotrigine 25 mg",
                    "Lamotrigine 25 mg",
                    "Depakote 500 mg",
                    "Depakote 500 mg",
                )
            )
        )
        == 1
    )


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        LamotrigineValproateChecker().check(_meds("Lamotrigine and valproate interaction warning"))
        == []
    )
    finding = ExportedChecker().check(_meds("Lamictal", "Divalproex"))[0]
    assert finding.severity is Severity.CRITICAL
