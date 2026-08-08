"""Tests for the SGLT2 + loop diuretic volume-depletion safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import Sglt2LoopChecker as ExportedChecker
from medagent.safety.sglt2_loop_checker import Sglt2LoopChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_without_sglt2() -> None:
    """Loop diuretic alone yields no SGLT2 × loop findings."""
    findings = Sglt2LoopChecker().check(
        _meds("Furosemide 40 mg daily"),
    )

    assert findings == []


def test_no_findings_with_sglt2_alone() -> None:
    """An SGLT2 inhibitor without a loop diuretic yields no findings."""
    findings = Sglt2LoopChecker().check(
        _meds("Empagliflozin 10 mg daily"),
    )

    assert findings == []


def test_flags_empagliflozin_plus_furosemide_high() -> None:
    """Empagliflozin + furosemide yields a HIGH finding."""
    findings = Sglt2LoopChecker().check(
        _meds("Empagliflozin 10 mg daily", "Furosemide 40 mg daily"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "empagliflozin"
    assert finding.partner_agent == "furosemide"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "volume" in finding.rationale.lower()


def test_flags_all_sglt2_and_loop_panel_agents() -> None:
    """Each panel SGLT2 and loop agent can participate in a finding."""
    sglt2_agents = [
        "empagliflozin",
        "dapagliflozin",
        "canagliflozin",
        "ertugliflozin",
    ]
    loop_agents = ["furosemide", "bumetanide", "torsemide", "ethacrynic"]

    for sglt2 in sglt2_agents:
        findings = Sglt2LoopChecker().check(
            _meds(f"{sglt2.title()} 10 mg", "Furosemide 20 mg"),
        )
        assert len(findings) == 1
        assert findings[0].agent == sglt2

    for loop in loop_agents:
        label = "Ethacrynic acid 25 mg" if loop == "ethacrynic" else f"{loop.title()} 1 mg"
        findings = Sglt2LoopChecker().check(
            _meds("Dapagliflozin 10 mg", label),
        )
        assert len(findings) == 1
        assert findings[0].partner_agent == loop


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match panel agents."""
    findings = Sglt2LoopChecker().check(
        _meds("Pseudoempagliflozin compound", "Furosemide 40 mg"),
    )

    assert findings == []
    real = Sglt2LoopChecker().check(
        _meds("Empagliflozin 10 mg", "Furosemide 40 mg"),
    )
    assert len(real) == 1


def test_duplicate_medication_entries_do_not_duplicate_pairs() -> None:
    """Duplicate list entries for the same agents do not duplicate pair findings."""
    findings = Sglt2LoopChecker().check(
        _meds(
            "Empagliflozin 10 mg daily",
            "Empagliflozin 25 mg daily",
            "Furosemide 40 mg daily",
        ),
    )

    assert len(findings) == 1


def test_multiple_loop_partners_produce_multiple_findings() -> None:
    """One SGLT2 with two loop partners yields two findings."""
    findings = Sglt2LoopChecker().check(
        _meds(
            "Canagliflozin 100 mg daily",
            "Furosemide 40 mg daily",
            "Bumetanide 1 mg daily",
        ),
    )

    assert len(findings) == 2
    partner_agents = {finding.partner_agent for finding in findings}
    assert partner_agents == {"furosemide", "bumetanide"}


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Empagliflozin 10 mg daily", "Furosemide 40 mg daily"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "empagliflozin"
    assert findings[0].partner_agent == "furosemide"
