"""Tests for the MAOI + serotonergic cross-check safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import MaoiSerotoninCrosscheckChecker as ExportedChecker
from medagent.safety.maoi_serotonin_checker import MaoiSerotoninCrosscheckChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_without_maoi() -> None:
    """SSRI + SSRI without MAOI yields no MAOI cross-check findings."""
    findings = MaoiSerotoninCrosscheckChecker().check(
        _meds("Sertraline 50 mg daily", "Fluoxetine 20 mg daily"),
    )

    assert findings == []


def test_no_findings_with_maoi_alone() -> None:
    """A lone MAOI without serotonergic partner yields no findings."""
    findings = MaoiSerotoninCrosscheckChecker().check(
        _meds("Phenelzine 15 mg TID"),
    )

    assert findings == []


def test_flags_maoi_plus_ssri() -> None:
    """MAOI + SSRI combination yields a CRITICAL finding."""
    findings = MaoiSerotoninCrosscheckChecker().check(
        _meds("Phenelzine 15 mg TID", "Sertraline 50 mg daily"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "phenelzine"
    assert finding.partner_agent == "sertraline"
    assert finding.partner_drug_class == "SSRI"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "contraindicated" in finding.rationale.lower()


def test_flags_linezolid_plus_snri() -> None:
    """Linezolid (reversible MAOI) + SNRI is flagged."""
    findings = MaoiSerotoninCrosscheckChecker().check(
        _meds("Linezolid 600 mg BID", "Venlafaxine 75 mg daily"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "linezolid"
    assert findings[0].partner_agent == "venlafaxine"
    assert findings[0].partner_drug_class == "SNRI"


def test_flags_maoi_plus_triptan() -> None:
    """MAOI + triptan combination is flagged."""
    findings = MaoiSerotoninCrosscheckChecker().check(
        _meds("Tranylcypromine 10 mg BID", "Sumatriptan 50 mg PRN"),
    )

    assert len(findings) == 1
    assert findings[0].partner_drug_class == "triptan"


def test_flags_maoi_plus_tramadol() -> None:
    """MAOI + serotonergic opioid is flagged."""
    findings = MaoiSerotoninCrosscheckChecker().check(
        _meds("Selegiline 5 mg daily", "Tramadol 50 mg QID"),
    )

    assert len(findings) == 1
    assert findings[0].partner_drug_class == "opioid"


def test_multiple_serotonergic_partners_produce_multiple_findings() -> None:
    """One MAOI with two serotonergic partners yields two findings."""
    findings = MaoiSerotoninCrosscheckChecker().check(
        _meds(
            "Phenelzine 15 mg TID",
            "Sertraline 50 mg daily",
            "Sumatriptan 50 mg PRN",
        ),
    )

    assert len(findings) == 2
    partner_agents = {finding.partner_agent for finding in findings}
    assert partner_agents == {"sertraline", "sumatriptan"}


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match panel agents."""
    findings = MaoiSerotoninCrosscheckChecker().check(
        _meds("Pseudophenelzine compound", "Sertraline 50 mg"),
    )

    assert findings == []
    real = MaoiSerotoninCrosscheckChecker().check(
        _meds("Phenelzine 15 mg", "Sertraline 50 mg"),
    )
    assert len(real) == 1


def test_duplicate_medication_entries_do_not_duplicate_pairs() -> None:
    """Duplicate list entries for the same agent do not duplicate pair findings."""
    findings = MaoiSerotoninCrosscheckChecker().check(
        _meds(
            "Phenelzine 15 mg TID",
            "Phenelzine 15 mg nightly",
            "Sertraline 50 mg daily",
        ),
    )

    assert len(findings) == 1


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Phenelzine 15 mg", "Fluoxetine 20 mg"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "phenelzine"
