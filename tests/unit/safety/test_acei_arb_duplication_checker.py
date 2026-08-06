"""Tests for the ACEI + ARB + ARNI dual-blockade duplication safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import AceiArbDuplicationChecker as ExportedChecker
from medagent.safety.acei_arb_duplication_checker import AceiArbDuplicationChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_with_single_acei() -> None:
    """A lone ACEI without ARB/ARNI partner yields no findings."""
    findings = AceiArbDuplicationChecker().check(
        _meds("Lisinopril 10 mg daily"),
    )

    assert findings == []


def test_no_findings_with_single_class_multiple_agents() -> None:
    """Two ACEIs alone do not constitute cross-class dual blockade."""
    findings = AceiArbDuplicationChecker().check(
        _meds("Lisinopril 10 mg daily", "Enalapril 5 mg daily"),
    )

    assert findings == []


def test_flags_acei_plus_arb_critical() -> None:
    """ACEI + ARB dual blockade yields CRITICAL severity."""
    findings = AceiArbDuplicationChecker().check(
        _meds("Lisinopril 10 mg daily", "Losartan 50 mg daily"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert {finding.class_a, finding.class_b} == {"ACEI", "ARB"}
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "dual" in finding.rationale.lower() or "blockade" in finding.rationale.lower()


def test_flags_acei_plus_arni_high() -> None:
    """ACEI + ARNI without ARB yields HIGH severity."""
    findings = AceiArbDuplicationChecker().check(
        _meds("Ramipril 5 mg daily", "Sacubitril 24 mg BID"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert {finding.class_a, finding.class_b} == {"ACEI", "ARNI"}
    assert finding.severity is Severity.HIGH
    assert finding.classes_present == ["ACEI", "ARNI"]


def test_flags_arb_plus_arni() -> None:
    """ARB + ARNI duplication is flagged."""
    findings = AceiArbDuplicationChecker().check(
        _meds("Olmesartan 20 mg daily", "Sacubitril 24 mg"),
    )

    assert len(findings) >= 1
    classes = set()
    for finding in findings:
        classes.update({finding.class_a, finding.class_b})
    assert "ARB" in classes
    assert "ARNI" in classes
    assert all(f.severity is Severity.HIGH for f in findings)


def test_flags_valsartan_olmesartan_with_lisinopril() -> None:
    """Multiple ARB partners with one ACEI produce multiple findings."""
    findings = AceiArbDuplicationChecker().check(
        _meds(
            "Lisinopril 20 mg daily",
            "Valsartan 80 mg daily",
            "Olmesartan 20 mg daily",
        ),
    )

    assert len(findings) == 2
    arb_agents = {
        finding.agent_a if finding.class_a == "ARB" else finding.agent_b for finding in findings
    }
    assert arb_agents == {"valsartan", "olmesartan"}
    assert all(f.severity is Severity.CRITICAL for f in findings)


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match panel agents."""
    findings = AceiArbDuplicationChecker().check(
        _meds("Pseudolisinopril compound", "Losartan 50 mg"),
    )

    assert findings == []
    real = AceiArbDuplicationChecker().check(
        _meds("Lisinopril 10 mg", "Losartan 50 mg"),
    )
    assert len(real) == 1


def test_duplicate_medication_entries_do_not_duplicate_pairs() -> None:
    """Duplicate list entries for the same agents do not duplicate pair findings."""
    findings = AceiArbDuplicationChecker().check(
        _meds(
            "Lisinopril 10 mg daily",
            "Lisinopril 20 mg daily",
            "Losartan 50 mg daily",
        ),
    )

    assert len(findings) == 1


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Enalapril 5 mg daily", "Losartan 50 mg daily"),
    )

    assert len(findings) == 1
    assert {findings[0].agent_a, findings[0].agent_b} == {"enalapril", "losartan"}
