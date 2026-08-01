"""Tests for the chemotherapy emetogenicity and antiemetic prophylaxis checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import ChemoEmesisChecker as ExportedChecker
from medagent.safety.chemo_emesis_checker import ChemoEmesisChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_without_chemo() -> None:
    """Non-chemotherapy medications yield no findings."""
    findings = ChemoEmesisChecker().check(
        _meds("Ondansetron 8 mg BID"),
        days_since_chemo=3,
    )

    assert findings == []


def test_no_findings_when_antiemetic_prophylaxis_present() -> None:
    """Emetogenic chemo with adequate antiemetic prophylaxis yields no findings."""
    findings = ChemoEmesisChecker().check(
        _meds("Cisplatin 75 mg/m2", "Ondansetron 8 mg BID", "Dexamethasone 12 mg"),
    )

    assert findings == []


def test_flags_missing_antiemetic_prophylaxis() -> None:
    """Highly emetogenic chemo without antiemetics is flagged CRITICAL."""
    findings = ChemoEmesisChecker().check(
        _meds("Cisplatin 75 mg/m2"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "cisplatin"
    assert finding.finding_kind == "missing_antiemetic_prophylaxis"
    assert finding.emetogenic_level == "high"
    assert finding.severity is Severity.CRITICAL
    assert finding.antiemetic_agents_found == []
    assert "RESEARCH USE ONLY" in finding.rationale


def test_moderate_emetogenic_missing_prophylaxis_is_high() -> None:
    """Moderately emetogenic chemo without antiemetics is flagged HIGH."""
    findings = ChemoEmesisChecker().check(
        _meds("Oxaliplatin 85 mg/m2"),
    )

    assert len(findings) == 1
    assert findings[0].severity is Severity.HIGH
    assert findings[0].emetogenic_level == "moderate"


def test_flags_delayed_phase_uncovered() -> None:
    """Delayed CINV window without delayed-phase coverage is flagged."""
    findings = ChemoEmesisChecker().check(
        _meds("Doxorubicin 60 mg/m2", "Ondansetron 8 mg BID"),
        days_since_chemo=3,
    )

    assert len(findings) == 1
    assert findings[0].finding_kind == "delayed_phase_uncovered"
    assert findings[0].days_since_chemo == 3
    assert findings[0].antiemetic_agents_found == ["ondansetron"]


def test_delayed_window_with_coverage_yields_no_delayed_finding() -> None:
    """Delayed-phase antiemetic coverage suppresses delayed_phase_uncovered."""
    findings = ChemoEmesisChecker().check(
        _meds("Cyclophosphamide 750 mg/m2", "Aprepitant 125 mg", "Dexamethasone 12 mg"),
        days_since_chemo=4,
    )

    assert findings == []


def test_missing_and_delayed_findings_can_coexist() -> None:
    """Chemo without antiemetics in delayed window yields both finding kinds."""
    findings = ChemoEmesisChecker().check(
        _meds("Ifosfamide 1.2 g/m2"),
        days_since_chemo=3,
    )

    kinds = {finding.finding_kind for finding in findings}
    assert kinds == {"missing_antiemetic_prophylaxis", "delayed_phase_uncovered"}


def test_outside_delayed_window_does_not_emit_delayed_finding() -> None:
    """Days outside the delayed window do not trigger delayed_phase_uncovered."""
    findings = ChemoEmesisChecker().check(
        _meds("Carboplatin AUC 5", "Ondansetron 8 mg BID"),
        days_since_chemo=1,
    )

    assert findings == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match panel agents."""
    findings = ChemoEmesisChecker().check(
        _meds("Pseudocisplatin compound"),
    )

    assert findings == []
    real = ChemoEmesisChecker().check(
        _meds("Cisplatin 75 mg/m2"),
    )
    assert len(real) == 1


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Dacarbazine 250 mg/m2"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "dacarbazine"
