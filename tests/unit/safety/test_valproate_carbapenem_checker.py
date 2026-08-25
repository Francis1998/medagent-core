"""Tests for the valproate + carbapenem precipitous level-drop checker."""

from medagent.models import Medication, Severity, ValproateCarbapenemRisk
from medagent.safety import ValproateCarbapenemChecker as ExportedChecker
from medagent.safety.valproate_carbapenem_checker import ValproateCarbapenemChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = ValproateCarbapenemChecker()
    assert checker.check(_meds("Depakote 500 mg")) == []
    assert checker.check(_meds("Meropenem 1 g")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = ValproateCarbapenemChecker().check(_meds("Depakote 500 mg", "Meropenem 1 g"))[0]

    assert isinstance(finding, ValproateCarbapenemRisk)
    assert finding.agent == "depakote"
    assert finding.partner_agent == "meropenem"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "seizure" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["valproate", "valproic acid", "divalproex", "depakote", "depakene"]:
        finding = ValproateCarbapenemChecker().check(
            _meds(f"{primary_agent} dose", "Meropenem 1 g")
        )[0]
        assert finding.agent == primary_agent

    for partner_agent, label in [
        ("meropenem", "Meropenem 1 g"),
        ("ertapenem", "Ertapenem 1 g"),
        ("imipenem", "Imipenem 500 mg"),
        ("doripenem", "Doripenem 500 mg"),
        ("carbapenem", "Carbapenem therapy"),
    ]:
        finding = ValproateCarbapenemChecker().check(_meds("Valproate 500 mg", label))[0]
        assert finding.partner_agent == partner_agent
        assert finding.severity is Severity.CRITICAL


def test_related_but_out_of_scope_agents_do_not_flag() -> None:
    checker = ValproateCarbapenemChecker()
    # Distinct from general AED screens and non-carbapenem beta-lactams
    for agent in ["Ceftriaxone", "Piperacillin", "Lamotrigine", "Carbamazepine"]:
        assert checker.check(_meds("Valproate 500 mg", agent)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = ValproateCarbapenemChecker()
    assert checker.check(_meds("Valproatelike", "Meropenemfree")) == []
    assert len(checker.check(_meds("Depakote", "Ertapenem"))) == 1
    assert len(checker.check(_meds("Valproic acid 250 mg", "Imipenem"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Meropenem 1 g", "Depakote 500 mg", "Ertapenem 1 g"]
    forward = ValproateCarbapenemChecker().check(_meds(*names))
    reverse = ValproateCarbapenemChecker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert (
        len(
            ValproateCarbapenemChecker().check(
                _meds(
                    "Depakote 500 mg",
                    "Depakote 500 mg",
                    "Meropenem 1 g",
                    "Meropenem 1 g",
                )
            )
        )
        == 1
    )


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        ValproateCarbapenemChecker().check(_meds("Valproate and meropenem interaction warning"))
        == []
    )
    finding = ExportedChecker().check(_meds("Depakene", "Doripenem"))[0]
    assert finding.severity is Severity.CRITICAL
