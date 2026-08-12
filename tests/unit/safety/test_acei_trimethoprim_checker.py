"""Tests for the ACEI/ARB + trimethoprim / TMP-SMX hyperkalemia checker."""

from __future__ import annotations

from medagent.models import AceiTrimethoprimRisk, Medication, Severity
from medagent.safety import AceiTrimethoprimChecker as ExportedChecker
from medagent.safety.acei_trimethoprim_checker import AceiTrimethoprimChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    """An ACEI/ARB or trimethoprim alone yields no finding."""
    checker = AceiTrimethoprimChecker()

    assert checker.check(_meds("Lisinopril 10 mg daily")) == []
    assert checker.check(_meds("Trimethoprim 100 mg BID")) == []
    assert checker.check([]) == []


def test_flags_lisinopril_plus_trimethoprim_high() -> None:
    """Lisinopril + trimethoprim yields a HIGH research-only finding."""
    findings = AceiTrimethoprimChecker().check(
        _meds("Lisinopril 10 mg daily", "Trimethoprim 100 mg BID")
    )

    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, AceiTrimethoprimRisk)
    assert finding.agent == "lisinopril"
    assert finding.partner_agent == "trimethoprim"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "hyperkalemia" in finding.rationale.lower()


def test_tmp_smx_brands_are_critical() -> None:
    """TMP-SMX brand/generic products escalate severity to CRITICAL."""
    for agent in ("bactrim", "septra", "cotrimoxazole"):
        finding = AceiTrimethoprimChecker().check(
            _meds("Losartan 50 mg daily", f"{agent.title()} DS BID")
        )[0]
        assert finding.partner_agent == agent
        assert finding.severity is Severity.CRITICAL


def test_all_acei_arb_panel_agents_participate() -> None:
    """Representative ACEI and ARB agents can produce findings."""
    agents = {
        "lisinopril": "ACEI",
        "enalapril": "ACEI",
        "losartan": "ARB",
        "valsartan": "ARB",
    }

    for agent in agents:
        finding = AceiTrimethoprimChecker().check(
            _meds(f"{agent.title()} 10 mg daily", "Trimethoprim 100 mg BID")
        )[0]
        assert finding.agent == agent
        assert finding.partner_agent == "trimethoprim"


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes do not match either medication panel."""
    checker = AceiTrimethoprimChecker()

    assert checker.check(_meds("Lisinoprillike", "Trimethoprimoid")) == []
    assert len(checker.check(_meds("Lisinopril 10 mg", "Trimethoprim 100 mg"))) == 1


def test_neighboring_interaction_controls_are_out_of_scope() -> None:
    """ACEI+K-sparing and MTX+TMP-SMX do not trigger without both target classes."""
    checker = AceiTrimethoprimChecker()

    assert checker.check(_meds("Lisinopril 10 mg", "Spironolactone 25 mg")) == []
    assert checker.check(_meds("Methotrexate 15 mg weekly", "Bactrim DS BID")) == []


def test_duplicate_entries_do_not_duplicate_canonical_pairs() -> None:
    """Duplicate entries for the same agents yield one canonical pair."""
    findings = AceiTrimethoprimChecker().check(
        _meds(
            "Lisinopril 10 mg daily",
            "Lisinopril 20 mg daily",
            "Trimethoprim 100 mg BID",
            "Trimethoprim 200 mg daily",
        )
    )

    assert len(findings) == 1


def test_findings_are_deterministic_across_input_order() -> None:
    """Multiple canonical pairs have stable medication/agent ordering."""
    names = [
        "Bactrim DS BID",
        "Lisinopril 10 mg daily",
        "Trimethoprim 100 mg BID",
        "Losartan 50 mg daily",
    ]
    checker = AceiTrimethoprimChecker()

    forward = checker.check(_meds(*names))
    reverse = checker.check(_meds(*reversed(names)))

    forward_pairs = [
        (finding.medication, finding.partner_medication, finding.agent, finding.partner_agent)
        for finding in forward
    ]
    reverse_pairs = [
        (finding.medication, finding.partner_medication, finding.agent, finding.partner_agent)
        for finding in reverse
    ]
    assert forward_pairs == reverse_pairs
    # CRITICAL TMP-SMX pairs sort before HIGH trimethoprim pairs.
    assert [(finding.agent, finding.partner_agent, finding.severity) for finding in forward] == [
        ("lisinopril", "bactrim", Severity.CRITICAL),
        ("losartan", "bactrim", Severity.CRITICAL),
        ("lisinopril", "trimethoprim", Severity.HIGH),
        ("losartan", "trimethoprim", Severity.HIGH),
    ]


def test_single_entry_is_not_treated_as_coprescription() -> None:
    """Two class names in one display string do not represent two prescriptions."""
    assert (
        AceiTrimethoprimChecker().check(_meds("Lisinopril and trimethoprim interaction note")) == []
    )


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(_meds("Valsartan 80 mg daily", "Septra DS BID"))

    assert len(findings) == 1
    assert findings[0].agent == "valsartan"
    assert findings[0].partner_agent == "septra"
    assert findings[0].severity is Severity.CRITICAL
