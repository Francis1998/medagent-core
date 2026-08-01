"""Tests for the opioid + benzodiazepine/Z-drug CNS depression safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import OpioidBenzoChecker as ExportedChecker
from medagent.safety.opioid_benzo_checker import OpioidBenzoChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_without_opioid() -> None:
    """Benzodiazepine alone yields no opioid × benzo findings."""
    findings = OpioidBenzoChecker().check(
        _meds("Lorazepam 1 mg BID"),
    )

    assert findings == []


def test_no_findings_with_opioid_alone() -> None:
    """A lone opioid without benzodiazepine partner yields no findings."""
    findings = OpioidBenzoChecker().check(
        _meds("Oxycodone 5 mg QID"),
    )

    assert findings == []


def test_flags_opioid_plus_benzodiazepine() -> None:
    """Opioid + benzodiazepine combination yields a CRITICAL finding."""
    findings = OpioidBenzoChecker().check(
        _meds("Oxycodone 5 mg QID", "Lorazepam 1 mg BID"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "oxycodone"
    assert finding.partner_agent == "lorazepam"
    assert finding.partner_drug_class == "benzodiazepine"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "respiratory depression" in finding.rationale.lower()


def test_flags_morphine_plus_z_drug() -> None:
    """Opioid + Z-drug hypnotic is flagged."""
    findings = OpioidBenzoChecker().check(
        _meds("Morphine 15 mg Q4H", "Zolpidem 10 mg nightly"),
    )

    assert len(findings) == 1
    assert findings[0].partner_drug_class == "Z-drug"


def test_flags_methadone_plus_clonazepam() -> None:
    """Methadone + clonazepam pair is flagged."""
    findings = OpioidBenzoChecker().check(
        _meds("Methadone 30 mg daily", "Clonazepam 0.5 mg BID"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "methadone"
    assert findings[0].partner_agent == "clonazepam"


def test_multiple_benzo_partners_produce_multiple_findings() -> None:
    """One opioid with two benzodiazepine partners yields two findings."""
    findings = OpioidBenzoChecker().check(
        _meds(
            "Hydrocodone 5 mg QID",
            "Diazepam 5 mg BID",
            "Temazepam 15 mg nightly",
        ),
    )

    assert len(findings) == 2
    partner_agents = {finding.partner_agent for finding in findings}
    assert partner_agents == {"diazepam", "temazepam"}


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match panel agents."""
    findings = OpioidBenzoChecker().check(
        _meds("Pseudooxycodone compound", "Lorazepam 1 mg"),
    )

    assert findings == []
    real = OpioidBenzoChecker().check(
        _meds("Oxycodone 5 mg", "Lorazepam 1 mg"),
    )
    assert len(real) == 1


def test_duplicate_medication_entries_do_not_duplicate_pairs() -> None:
    """Duplicate list entries for the same agent do not duplicate pair findings."""
    findings = OpioidBenzoChecker().check(
        _meds(
            "Fentanyl patch 25 mcg/hr",
            "Fentanyl patch 50 mcg/hr",
            "Alprazolam 0.5 mg TID",
        ),
    )

    assert len(findings) == 1


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Tramadol 50 mg QID", "Eszopiclone 2 mg nightly"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "tramadol"
