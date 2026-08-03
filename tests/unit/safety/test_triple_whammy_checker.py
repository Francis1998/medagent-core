"""Tests for the NSAID + ACEI/ARB/ARNI + diuretic triple whammy checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import TripleWhammyChecker as ExportedChecker
from medagent.safety.triple_whammy_checker import TripleWhammyChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_without_nsaid() -> None:
    """ACEI + diuretic without NSAID yields no findings."""
    findings = TripleWhammyChecker().check(
        _meds("Lisinopril 10 mg daily", "Furosemide 40 mg BID"),
    )

    assert findings == []


def test_no_findings_without_acei_arb() -> None:
    """NSAID + diuretic without ACEI/ARB/ARNI yields no findings."""
    findings = TripleWhammyChecker().check(
        _meds("Ibuprofen 400 mg TID", "Furosemide 40 mg BID"),
    )

    assert findings == []


def test_no_findings_without_diuretic() -> None:
    """NSAID + ACEI without diuretic yields no findings."""
    findings = TripleWhammyChecker().check(
        _meds("Ibuprofen 400 mg TID", "Lisinopril 10 mg daily"),
    )

    assert findings == []


def test_flags_classic_triple_whammy_critical() -> None:
    """Ibuprofen + lisinopril + furosemide yields a CRITICAL finding."""
    findings = TripleWhammyChecker().check(
        _meds(
            "Ibuprofen 400 mg TID",
            "Lisinopril 10 mg daily",
            "Furosemide 40 mg BID",
        ),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.nsaid_agent == "ibuprofen"
    assert finding.acei_arb_agent == "lisinopril"
    assert finding.diuretic_agent == "furosemide"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "triple whammy" in finding.rationale.lower()


def test_flags_arb_and_thiazide_combination() -> None:
    """Naproxen + losartan + hydrochlorothiazide is flagged."""
    findings = TripleWhammyChecker().check(
        _meds(
            "Naproxen 500 mg BID",
            "Losartan 50 mg daily",
            "Hydrochlorothiazide 25 mg daily",
        ),
    )

    assert len(findings) == 1
    assert findings[0].acei_arb_agent == "losartan"
    assert findings[0].diuretic_agent == "hydrochlorothiazide"


def test_flags_sacubitril_arni_and_hctz_abbreviation() -> None:
    """Diclofenac + sacubitril + HCTZ abbreviation is flagged."""
    findings = TripleWhammyChecker().check(
        _meds(
            "Diclofenac 50 mg BID",
            "Sacubitril/Valsartan 97/103 mg BID",
            "HCTZ 12.5 mg daily",
        ),
    )

    assert len(findings) == 1
    assert findings[0].acei_arb_agent == "sacubitril"
    assert findings[0].diuretic_agent == "hctz"


def test_flags_ketorolac_meloxicam_and_chlorthalidone() -> None:
    """Ketorolac + ramipril + chlorthalidone is flagged."""
    findings = TripleWhammyChecker().check(
        _meds(
            "Ketorolac 10 mg QID",
            "Ramipril 5 mg daily",
            "Chlorthalidone 25 mg daily",
        ),
    )

    assert len(findings) == 1
    assert findings[0].nsaid_agent == "ketorolac"
    assert findings[0].diuretic_agent == "chlorthalidone"


def test_multiple_nsaids_produce_multiple_findings() -> None:
    """Two NSAIDs with ACEI and diuretic yield two triad findings."""
    findings = TripleWhammyChecker().check(
        _meds(
            "Ibuprofen 400 mg TID",
            "Meloxicam 15 mg daily",
            "Enalapril 10 mg daily",
            "Bumetanide 1 mg daily",
        ),
    )

    assert len(findings) == 2
    nsaid_agents = {finding.nsaid_agent for finding in findings}
    assert nsaid_agents == {"ibuprofen", "meloxicam"}


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match panel agents."""
    findings = TripleWhammyChecker().check(
        _meds(
            "Pseudoibuprofen compound",
            "Lisinopril 10 mg",
            "Furosemide 40 mg",
        ),
    )

    assert findings == []
    real = TripleWhammyChecker().check(
        _meds(
            "Ibuprofen 400 mg",
            "Lisinopril 10 mg",
            "Furosemide 40 mg",
        ),
    )
    assert len(real) == 1


def test_duplicate_medication_entries_do_not_duplicate_triads() -> None:
    """Duplicate list entries for the same agents do not duplicate findings."""
    findings = TripleWhammyChecker().check(
        _meds(
            "Ibuprofen 200 mg",
            "Ibuprofen 400 mg",
            "Lisinopril 10 mg daily",
            "Furosemide 20 mg",
            "Furosemide 40 mg",
        ),
    )

    assert len(findings) == 1


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds(
            "Naproxen 250 mg BID",
            "Valsartan 80 mg daily",
            "Torsemide 10 mg daily",
        ),
    )

    assert len(findings) == 1
    assert findings[0].nsaid_agent == "naproxen"
    assert findings[0].acei_arb_agent == "valsartan"
    assert findings[0].diuretic_agent == "torsemide"
