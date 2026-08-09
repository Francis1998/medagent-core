"""Tests for the DOAC + antiplatelet bleed intensifier safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import DoacAntiplateletChecker as ExportedChecker
from medagent.safety.doac_antiplatelet_checker import DoacAntiplateletChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_without_doac() -> None:
    """Antiplatelet alone yields no DOAC × antiplatelet findings."""
    findings = DoacAntiplateletChecker().check(
        _meds("Aspirin 81 mg daily"),
    )

    assert findings == []


def test_no_findings_with_doac_alone() -> None:
    """DOAC without an antiplatelet yields no findings."""
    findings = DoacAntiplateletChecker().check(
        _meds("Apixaban 5 mg BID"),
    )

    assert findings == []


def test_flags_apixaban_plus_aspirin_high() -> None:
    """Apixaban + aspirin yields a HIGH finding."""
    findings = DoacAntiplateletChecker().check(
        _meds("Apixaban 5 mg BID", "Aspirin 81 mg daily"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "apixaban"
    assert finding.partner_agent == "aspirin"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "bleeding" in finding.rationale.lower()


def test_flags_all_doac_and_antiplatelet_panel_agents() -> None:
    """Each DOAC and antiplatelet panel agent can participate in a finding."""
    doacs = ["apixaban", "rivaroxaban", "edoxaban", "dabigatran"]
    antiplatelets = ["aspirin", "clopidogrel", "prasugrel", "ticagrelor"]

    for doac in doacs:
        findings = DoacAntiplateletChecker().check(
            _meds(f"{doac.title()} 5 mg", "Clopidogrel 75 mg daily"),
        )
        assert len(findings) == 1
        assert findings[0].agent == doac
        assert findings[0].severity is Severity.HIGH

    for antiplatelet in antiplatelets:
        findings = DoacAntiplateletChecker().check(
            _meds("Rivaroxaban 20 mg daily", f"{antiplatelet.title()} 75 mg"),
        )
        assert len(findings) == 1
        assert findings[0].partner_agent == antiplatelet


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match panel agents."""
    findings = DoacAntiplateletChecker().check(
        _meds("Pseudoapixaban compound", "Aspirinoid supplement"),
    )

    assert findings == []
    real = DoacAntiplateletChecker().check(
        _meds("Apixaban 5 mg BID", "Aspirin 81 mg daily"),
    )
    assert len(real) == 1


def test_duplicate_medication_entries_do_not_duplicate_pairs() -> None:
    """Duplicate list entries for the same agents do not duplicate pair findings."""
    findings = DoacAntiplateletChecker().check(
        _meds(
            "Apixaban 5 mg BID",
            "Apixaban 2.5 mg BID",
            "Clopidogrel 75 mg daily",
        ),
    )

    assert len(findings) == 1


def test_multiple_antiplatelet_partners_produce_multiple_findings() -> None:
    """One DOAC with two antiplatelet partners yields two findings."""
    findings = DoacAntiplateletChecker().check(
        _meds(
            "Dabigatran 150 mg BID",
            "Aspirin 81 mg daily",
            "Ticagrelor 90 mg BID",
        ),
    )

    assert len(findings) == 2
    partner_agents = {finding.partner_agent for finding in findings}
    assert partner_agents == {"aspirin", "ticagrelor"}


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Apixaban 5 mg BID", "Aspirin 81 mg daily"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "apixaban"
    assert findings[0].partner_agent == "aspirin"
