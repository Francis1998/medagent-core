"""Tests for the amiodarone + warfarin INR interaction safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import AmioWarfarinChecker as ExportedChecker
from medagent.safety.amio_warfarin_checker import AmioWarfarinChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_without_amiodarone() -> None:
    """Warfarin alone yields no amiodarone × warfarin findings."""
    findings = AmioWarfarinChecker().check(
        _meds("Warfarin 5 mg daily"),
    )

    assert findings == []


def test_no_findings_with_amiodarone_alone() -> None:
    """Amiodarone without warfarin yields no findings."""
    findings = AmioWarfarinChecker().check(
        _meds("Amiodarone 200 mg daily"),
    )

    assert findings == []


def test_flags_amiodarone_plus_warfarin_high() -> None:
    """Amiodarone + warfarin yields a HIGH finding."""
    findings = AmioWarfarinChecker().check(
        _meds("Amiodarone 200 mg daily", "Warfarin 5 mg daily"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "amiodarone"
    assert finding.partner_agent == "warfarin"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "inr" in finding.rationale.lower()


def test_flags_all_amiodarone_and_warfarin_panel_agents() -> None:
    """Each amiodarone-class and warfarin-class panel agent can participate."""
    amio_agents = ["amiodarone", "cordarone", "pacerone"]
    warfarin_agents = ["warfarin", "coumadin", "jantoven"]

    for amio_agent in amio_agents:
        findings = AmioWarfarinChecker().check(
            _meds(f"{amio_agent.title()} 200 mg", "Warfarin 5 mg daily"),
        )
        assert len(findings) == 1
        assert findings[0].agent == amio_agent
        assert findings[0].severity is Severity.HIGH

    for warfarin_agent in warfarin_agents:
        findings = AmioWarfarinChecker().check(
            _meds("Cordarone 200 mg daily", f"{warfarin_agent.title()} 5 mg"),
        )
        assert len(findings) == 1
        assert findings[0].partner_agent == warfarin_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match panel agents."""
    findings = AmioWarfarinChecker().check(
        _meds("Pseudoamiodarone compound", "Warfarinoid supplement"),
    )

    assert findings == []
    real = AmioWarfarinChecker().check(
        _meds("Amiodarone 200 mg daily", "Warfarin 5 mg daily"),
    )
    assert len(real) == 1


def test_duplicate_medication_entries_do_not_duplicate_pairs() -> None:
    """Duplicate list entries for the same agents do not duplicate pair findings."""
    findings = AmioWarfarinChecker().check(
        _meds(
            "Amiodarone 200 mg daily",
            "Amiodarone 100 mg daily",
            "Coumadin 5 mg daily",
        ),
    )

    assert len(findings) == 1


def test_multiple_warfarin_partners_produce_multiple_findings() -> None:
    """One amiodarone with two warfarin-class partners yields two findings."""
    findings = AmioWarfarinChecker().check(
        _meds(
            "Pacerone 200 mg daily",
            "Warfarin 5 mg daily",
            "Jantoven 2.5 mg daily",
        ),
    )

    assert len(findings) == 2
    partner_agents = {finding.partner_agent for finding in findings}
    assert partner_agents == {"warfarin", "jantoven"}


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Amiodarone 200 mg daily", "Warfarin 5 mg daily"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "amiodarone"
    assert findings[0].partner_agent == "warfarin"
