"""Tests for the tizanidine + strong CYP1A2 inhibitor hypotension / sedation checker."""

from medagent.models import Medication, Severity, TizanidineCiproRisk
from medagent.safety import TizanidineCiproChecker as ExportedChecker
from medagent.safety.tizanidine_cipro_checker import TizanidineCiproChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = TizanidineCiproChecker()
    assert checker.check(_meds("Tizanidine 4 mg TID")) == []
    assert checker.check(_meds("Ciprofloxacin 500 mg BID")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = TizanidineCiproChecker().check(
        _meds("Tizanidine 4 mg TID", "Ciprofloxacin 500 mg BID")
    )[0]

    assert isinstance(finding, TizanidineCiproRisk)
    assert finding.agent == "tizanidine"
    assert finding.partner_agent == "ciprofloxacin"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "hypotension" in finding.rationale.lower() or "sedation" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["tizanidine", "zanaflex"]:
        finding = TizanidineCiproChecker().check(
            _meds(f"{primary_agent} dose", "Ciprofloxacin 500 mg")
        )[0]
        assert finding.agent == primary_agent

    for partner_agent, label in [
        ("ciprofloxacin", "Ciprofloxacin 500 mg"),
        ("cipro", "Cipro 500 mg"),
        ("fluvoxamine", "Fluvoxamine 100 mg"),
        ("luvox", "Luvox 100 mg"),
    ]:
        finding = TizanidineCiproChecker().check(_meds("Tizanidine 4 mg", label))[0]
        assert finding.partner_agent == partner_agent
        assert finding.severity is Severity.CRITICAL


def test_related_but_out_of_scope_agents_do_not_flag() -> None:
    checker = TizanidineCiproChecker()
    # Distinct from theophylline + cipro and clozapine CYP1A2
    for agent in ["Levofloxacin", "Clozapine", "Theophylline", "Enoxacin"]:
        assert checker.check(_meds("Tizanidine 4 mg", agent)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = TizanidineCiproChecker()
    assert checker.check(_meds("Tizanidinelike", "Ciprofloxacinfrees")) == []
    assert len(checker.check(_meds("Tizanidine", "Ciprofloxacin"))) == 1
    assert len(checker.check(_meds("Zanaflex", "Cipro"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Cipro 500 mg", "Tizanidine 4 mg", "Fluvoxamine 100 mg"]
    forward = TizanidineCiproChecker().check(_meds(*names))
    reverse = TizanidineCiproChecker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert (
        len(
            TizanidineCiproChecker().check(
                _meds(
                    "Tizanidine 4 mg",
                    "Tizanidine 2 mg",
                    "Ciprofloxacin 500 mg",
                    "Ciprofloxacin 250 mg",
                )
            )
        )
        == 1
    )


def test_findings_sorted_deterministically_by_partner() -> None:
    findings = TizanidineCiproChecker().check(
        _meds("Tizanidine 4 mg", "Fluvoxamine 100 mg", "Ciprofloxacin 500 mg")
    )
    assert all(finding.severity is Severity.CRITICAL for finding in findings)
    assert [finding.partner_agent for finding in findings] == ["ciprofloxacin", "fluvoxamine"]


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        TizanidineCiproChecker().check(_meds("Tizanidine and ciprofloxacin interaction warning"))
        == []
    )
    finding = ExportedChecker().check(_meds("Zanaflex 4 mg", "Luvox 100 mg"))[0]
    assert finding.agent == "zanaflex"
    assert finding.partner_agent == "luvox"
    assert finding.severity is Severity.CRITICAL
