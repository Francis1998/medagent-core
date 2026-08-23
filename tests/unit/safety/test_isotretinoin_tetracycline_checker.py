"""Tests for the isotretinoin + tetracycline-class pseudotumor cerebri checker."""

from medagent.models import IsotretinoinTetracyclineRisk, Medication, Severity
from medagent.safety import IsotretinoinTetracyclineChecker as ExportedChecker
from medagent.safety.isotretinoin_tetracycline_checker import (
    IsotretinoinTetracyclineChecker,
)


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = IsotretinoinTetracyclineChecker()
    assert checker.check(_meds("Isotretinoin 40 mg")) == []
    assert checker.check(_meds("Doxycycline 100 mg")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = IsotretinoinTetracyclineChecker().check(
        _meds("Isotretinoin 40 mg", "Doxycycline 100 mg")
    )[0]

    assert isinstance(finding, IsotretinoinTetracyclineRisk)
    assert finding.agent == "isotretinoin"
    assert finding.partner_agent == "doxycycline"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "pseudotumor cerebri" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["isotretinoin", "accutane", "absorica", "claravis", "myorisan"]:
        finding = IsotretinoinTetracyclineChecker().check(
            _meds(f"{primary_agent} dose", "Minocycline 100 mg")
        )[0]
        assert finding.agent == primary_agent

    for partner_agent, label in [
        ("tetracycline", "Tetracycline 500 mg"),
        ("doxycycline", "Doxycycline 100 mg"),
        ("minocycline", "Minocycline 100 mg"),
    ]:
        finding = IsotretinoinTetracyclineChecker().check(_meds("Isotretinoin 40 mg", label))[0]
        assert finding.partner_agent == partner_agent
        assert finding.severity is Severity.CRITICAL


def test_related_but_out_of_scope_agents_do_not_flag() -> None:
    checker = IsotretinoinTetracyclineChecker()
    for agent in ["Amoxicillin", "Clindamycin", "Oxytetracycline", "Benzoyl Peroxide"]:
        assert checker.check(_meds("Isotretinoin 40 mg", agent)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = IsotretinoinTetracyclineChecker()
    assert checker.check(_meds("Isotretinoinlike", "Doxycyclinefree")) == []
    assert len(checker.check(_meds("Accutane", "Minocycline"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Doxycycline 100 mg", "Isotretinoin 40 mg", "Minocycline 100 mg"]
    forward = IsotretinoinTetracyclineChecker().check(_meds(*names))
    reverse = IsotretinoinTetracyclineChecker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert [item.partner_agent for item in forward] == ["doxycycline", "minocycline"]
    assert (
        len(
            IsotretinoinTetracyclineChecker().check(
                _meds(
                    "Isotretinoin 40 mg",
                    "Isotretinoin 40 mg",
                    "Doxycycline 100 mg",
                    "Doxycycline 100 mg",
                )
            )
        )
        == 1
    )


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        IsotretinoinTetracyclineChecker().check(
            _meds("Isotretinoin and doxycycline interaction warning")
        )
        == []
    )
    finding = ExportedChecker().check(_meds("Claravis", "Tetracycline"))[0]
    assert finding.severity is Severity.CRITICAL
