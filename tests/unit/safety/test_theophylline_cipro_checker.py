"""Tests for the theophylline + CYP1A2-inhibiting quinolone checker."""

from medagent.models import Medication, Severity, TheophyllineCiproRisk
from medagent.safety import TheophyllineCiproChecker as ExportedChecker
from medagent.safety.theophylline_cipro_checker import TheophyllineCiproChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = TheophyllineCiproChecker()
    assert checker.check(_meds("Theophylline 300 mg daily")) == []
    assert checker.check(_meds("Ciprofloxacin 500 mg BID")) == []
    assert checker.check([]) == []


def test_flags_theophylline_plus_ciprofloxacin_high() -> None:
    finding = TheophyllineCiproChecker().check(
        _meds("Theophylline 300 mg daily", "Ciprofloxacin 500 mg BID")
    )[0]

    assert isinstance(finding, TheophyllineCiproRisk)
    assert finding.agent == "theophylline"
    assert finding.partner_agent == "ciprofloxacin"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "CYP1A2" in finding.rationale


def test_enoxacin_is_critical() -> None:
    finding = TheophyllineCiproChecker().check(
        _meds("Theophylline 300 mg daily", "Enoxacin 400 mg BID")
    )[0]
    assert finding.partner_agent == "enoxacin"
    assert finding.severity is Severity.CRITICAL


def test_supported_theophylline_and_ciprofloxacin_aliases_participate() -> None:
    for agent in ["theophylline", "aminophylline", "uniphyl", "theochron"]:
        finding = TheophyllineCiproChecker().check(
            _meds(f"{agent.title()} 300 mg", "Ciprofloxacin 500 mg")
        )[0]
        assert finding.agent == agent

    cipro = TheophyllineCiproChecker().check(_meds("Theophylline 300 mg", "Cipro 500 mg"))[0]
    assert cipro.partner_agent == "cipro"
    assert cipro.severity is Severity.HIGH


def test_other_fluoroquinolones_are_out_of_scope() -> None:
    checker = TheophyllineCiproChecker()
    for antibiotic in ["Levofloxacin", "Moxifloxacin", "Ofloxacin"]:
        assert checker.check(_meds("Theophylline 300 mg", antibiotic)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = TheophyllineCiproChecker()
    assert checker.check(_meds("Theophyllinelike", "Ciprofloxacinoid")) == []
    assert len(checker.check(_meds("Theophylline", "Ciprofloxacin"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Enoxacin 400 mg", "Theophylline 300 mg", "Ciprofloxacin 500 mg"]
    forward = TheophyllineCiproChecker().check(_meds(*names))
    reverse = TheophyllineCiproChecker().check(_meds(*reversed(names)))

    assert [
        (item.agent, item.partner_agent, item.severity, item.partner_medication)
        for item in forward
    ] == [
        (item.agent, item.partner_agent, item.severity, item.partner_medication)
        for item in reverse
    ]
    assert [(item.partner_agent, item.severity) for item in forward] == [
        ("enoxacin", Severity.CRITICAL),
        ("ciprofloxacin", Severity.HIGH),
    ]
    assert (
        len(
            TheophyllineCiproChecker().check(
                _meds(
                    "Theophylline 300 mg",
                    "Theophylline 200 mg",
                    "Ciprofloxacin 500 mg",
                    "Ciprofloxacin 250 mg",
                )
            )
        )
        == 1
    )


def test_single_entry_is_not_coprescription() -> None:
    assert (
        TheophyllineCiproChecker().check(
            _meds("Theophylline and ciprofloxacin interaction warning")
        )
        == []
    )


def test_checker_is_exported_from_safety_package() -> None:
    finding = ExportedChecker().check(_meds("Uniphyl 300 mg", "Cipro 500 mg"))[0]
    assert finding.agent == "uniphyl"
    assert finding.partner_agent == "cipro"
