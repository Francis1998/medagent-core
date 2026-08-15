"""Tests for the SGLT2 + ACEI/ARB/ARNI safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity, Sglt2RaasiRisk
from medagent.safety import Sglt2RaasiChecker as ExportedChecker
from medagent.safety.sglt2_raasi_checker import Sglt2RaasiChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    """SGLT2 inhibitor or RAASI alone yields no finding."""
    checker = Sglt2RaasiChecker()

    assert checker.check(_meds("Empagliflozin 10 mg daily")) == []
    assert checker.check(_meds("Lisinopril 10 mg daily")) == []
    assert checker.check([]) == []


def test_flags_empagliflozin_plus_lisinopril_high() -> None:
    """Empagliflozin + lisinopril yields a HIGH research-only finding."""
    findings = Sglt2RaasiChecker().check(
        _meds("Empagliflozin 10 mg daily", "Lisinopril 10 mg daily")
    )

    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, Sglt2RaasiRisk)
    assert finding.agent == "empagliflozin"
    assert finding.partner_agent == "lisinopril"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "hyperkalemia" in finding.rationale.lower()


def test_entresto_plus_dapagliflozin_is_high() -> None:
    """Entresto + dapagliflozin yields HIGH severity."""
    finding = Sglt2RaasiChecker().check(
        _meds("Dapagliflozin 10 mg daily", "Entresto 24/26 mg BID")
    )[0]

    assert finding.agent == "dapagliflozin"
    assert finding.partner_agent == "entresto"
    assert finding.severity is Severity.HIGH


def test_all_supported_sglt2_agents_participate() -> None:
    """Every supported SGLT2 token can produce a finding with a RAASI partner."""
    for sglt2_agent in ["empagliflozin", "dapagliflozin", "canagliflozin", "ertugliflozin"]:
        finding = Sglt2RaasiChecker().check(
            _meds(f"{sglt2_agent.title()} 10 mg", "Losartan 50 mg")
        )[0]
        assert finding.agent == sglt2_agent


def test_representative_raasi_partners() -> None:
    """ACEI, ARB, and ARNI partners can participate in findings."""
    checker = Sglt2RaasiChecker()

    assert (
        checker.check(_meds("Empagliflozin 10 mg", "Ramipril 5 mg"))[0].partner_agent == "ramipril"
    )
    assert (
        checker.check(_meds("Empagliflozin 10 mg", "Valsartan 80 mg"))[0].partner_agent
        == "valsartan"
    )
    assert (
        checker.check(_meds("Empagliflozin 10 mg", "Sacubitril 24 mg"))[0].partner_agent
        == "sacubitril"
    )


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes do not match either medication panel."""
    checker = Sglt2RaasiChecker()

    assert checker.check(_meds("Pseudoempagliflozin compound", "Lisinopriloid supplement")) == []
    assert len(checker.check(_meds("Empagliflozin 10 mg", "Lisinopril 10 mg"))) == 1


def test_duplicate_entries_do_not_duplicate_canonical_pairs() -> None:
    """Duplicate entries for the same agents yield one canonical pair."""
    findings = Sglt2RaasiChecker().check(
        _meds(
            "Empagliflozin 10 mg",
            "Empagliflozin 25 mg",
            "Lisinopril 5 mg",
            "Lisinopril 10 mg",
        )
    )

    assert len(findings) == 1


def test_single_entry_is_not_treated_as_coprescription() -> None:
    """Two class names in one display string do not represent two prescriptions."""
    assert Sglt2RaasiChecker().check(_meds("Empagliflozin and lisinopril interaction note")) == []


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    finding = ExportedChecker().check(_meds("Canagliflozin 100 mg", "Olmesartan 20 mg"))[0]

    assert finding.agent == "canagliflozin"
    assert finding.partner_agent == "olmesartan"
    assert finding.severity is Severity.HIGH
