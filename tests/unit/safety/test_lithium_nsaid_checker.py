"""Tests for the lithium + NSAID toxicity interaction safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import LithiumNsaidChecker as ExportedChecker
from medagent.safety.lithium_nsaid_checker import LithiumNsaidChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_without_lithium() -> None:
    """NSAID alone yields no lithium × NSAID findings."""
    findings = LithiumNsaidChecker().check(
        _meds("Ibuprofen 400 mg TID PRN"),
    )

    assert findings == []


def test_no_findings_with_lithium_alone() -> None:
    """Lithium without an NSAID yields no findings."""
    findings = LithiumNsaidChecker().check(
        _meds("Lithium carbonate 300 mg BID"),
    )

    assert findings == []


def test_acetaminophen_alone_is_not_flagged() -> None:
    """Acetaminophen alone is not part of the NSAID interaction panel."""
    findings = LithiumNsaidChecker().check(
        _meds("Acetaminophen 650 mg every 6 hours PRN"),
    )

    assert findings == []


def test_acetaminophen_and_paracetamol_are_not_nsaids() -> None:
    """Lithium with acetaminophen/paracetamol should not yield NSAID findings."""
    findings = LithiumNsaidChecker().check(
        _meds(
            "Lithium carbonate 300 mg BID",
            "Acetaminophen 650 mg PRN",
            "Paracetamol 500 mg PRN",
        ),
    )

    assert findings == []


def test_flags_lithium_plus_ibuprofen_high() -> None:
    """Lithium + ibuprofen yields a HIGH finding."""
    findings = LithiumNsaidChecker().check(
        _meds("Lithium carbonate 300 mg BID", "Ibuprofen 400 mg TID PRN"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "lithium"
    assert finding.partner_agent == "ibuprofen"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "lithium toxicity" in finding.rationale.lower()


def test_flags_all_lithium_and_nsaid_panel_agents() -> None:
    """Each lithium-class and NSAID panel agent can participate in a finding."""
    lithium_agents = ["lithium", "lithobid", "eskalith"]
    nsaid_agents = [
        "ibuprofen",
        "naproxen",
        "diclofenac",
        "indomethacin",
        "ketorolac",
        "meloxicam",
        "piroxicam",
        "celecoxib",
    ]

    for lithium_agent in lithium_agents:
        findings = LithiumNsaidChecker().check(
            _meds(f"{lithium_agent.title()} 300 mg", "Naproxen 250 mg BID"),
        )
        assert len(findings) == 1
        assert findings[0].agent == lithium_agent

    for nsaid_agent in nsaid_agents:
        findings = LithiumNsaidChecker().check(
            _meds("Lithobid 300 mg BID", f"{nsaid_agent.title()} 100 mg"),
        )
        assert len(findings) == 1
        assert findings[0].partner_agent == nsaid_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match panel agents."""
    findings = LithiumNsaidChecker().check(
        _meds("Pseudolithium compound", "Ibuprofenoid supplement"),
    )

    assert findings == []
    real = LithiumNsaidChecker().check(
        _meds("Lithium 300 mg", "Ibuprofen 400 mg"),
    )
    assert len(real) == 1


def test_duplicate_medication_entries_do_not_duplicate_pairs() -> None:
    """Duplicate list entries for the same agents do not duplicate pair findings."""
    findings = LithiumNsaidChecker().check(
        _meds(
            "Lithium carbonate 300 mg BID",
            "Lithium carbonate 150 mg daily",
            "Ibuprofen 400 mg TID PRN",
        ),
    )

    assert len(findings) == 1


def test_multiple_nsaid_partners_produce_multiple_findings() -> None:
    """One lithium-class agent with two NSAID partners yields two findings."""
    findings = LithiumNsaidChecker().check(
        _meds(
            "Eskalith 300 mg BID",
            "Ibuprofen 400 mg TID PRN",
            "Celecoxib 100 mg BID",
        ),
    )

    assert len(findings) == 2
    partner_agents = {finding.partner_agent for finding in findings}
    assert partner_agents == {"ibuprofen", "celecoxib"}


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Lithium carbonate 300 mg BID", "Ibuprofen 400 mg TID PRN"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "lithium"
    assert findings[0].partner_agent == "ibuprofen"
