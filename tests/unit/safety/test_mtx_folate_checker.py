"""Tests for the methotrexate without folate co-therapy safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import MtxFolateChecker as ExportedChecker
from medagent.safety.mtx_folate_checker import MtxFolateChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_without_methotrexate() -> None:
    """Non-MTX medications yield no findings."""
    findings = MtxFolateChecker().check(
        _meds("Prednisone 5 mg daily", "Folic acid 1 mg daily"),
    )

    assert findings == []


def test_no_findings_when_folic_acid_present() -> None:
    """Methotrexate with folic acid co-therapy yields no findings."""
    findings = MtxFolateChecker().check(
        _meds("Methotrexate 15 mg weekly", "Folic acid 1 mg daily"),
    )

    assert findings == []


def test_no_findings_when_folate_present() -> None:
    """Methotrexate with folate co-therapy yields no findings."""
    findings = MtxFolateChecker().check(
        _meds("Methotrexate 10 mg weekly", "Folate 1 mg daily"),
    )

    assert findings == []


def test_no_findings_when_leucovorin_present() -> None:
    """Methotrexate with leucovorin co-therapy yields no findings."""
    findings = MtxFolateChecker().check(
        _meds("Methotrexate 50 mg/m2", "Leucovorin 15 mg Q6H"),
    )

    assert findings == []


def test_flags_methotrexate_without_folate_high() -> None:
    """Methotrexate alone is flagged HIGH for missing folate co-therapy."""
    findings = MtxFolateChecker().check(
        _meds("Methotrexate 15 mg weekly", "Prednisone 5 mg daily"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "methotrexate"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "folate" in finding.rationale.lower() or "folic" in finding.rationale.lower()


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match methotrexate."""
    findings = MtxFolateChecker().check(
        _meds("Pseudomethotrexate compound"),
    )

    assert findings == []
    real = MtxFolateChecker().check(
        _meds("Methotrexate 15 mg weekly"),
    )
    assert len(real) == 1


def test_duplicate_medication_entries_do_not_duplicate_findings() -> None:
    """Duplicate methotrexate entries do not duplicate findings."""
    findings = MtxFolateChecker().check(
        _meds(
            "Methotrexate 10 mg weekly",
            "Methotrexate 15 mg weekly",
        ),
    )

    assert len(findings) == 1


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Methotrexate 20 mg weekly"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "methotrexate"
