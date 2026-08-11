"""Tests for the ACEI/ARB + potassium-sparing hyperkalemia checker."""

from __future__ import annotations

from medagent.models import AceiKsparingRisk, Medication, Severity
from medagent.safety import AceiKsparingChecker as ExportedChecker
from medagent.safety.acei_ksparing_checker import AceiKsparingChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    """An ACEI/ARB or potassium-sparing agent alone yields no finding."""
    checker = AceiKsparingChecker()

    assert checker.check(_meds("Lisinopril 20 mg daily")) == []
    assert checker.check(_meds("Spironolactone 25 mg daily")) == []
    assert checker.check([]) == []


def test_flags_lisinopril_plus_spironolactone_high() -> None:
    """Lisinopril + spironolactone yields a HIGH research-only finding."""
    findings = AceiKsparingChecker().check(
        _meds("Lisinopril 20 mg daily", "Spironolactone 25 mg daily")
    )

    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, AceiKsparingRisk)
    assert finding.agent == "lisinopril"
    assert finding.partner_agent == "spironolactone"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "hyperkalemia" in finding.rationale.lower()
    assert "renal" in finding.rationale.lower()


def test_all_acei_arb_panel_agents_participate() -> None:
    """Every supported ACEI and ARB can produce a finding."""
    acei_arb_agents = [
        "lisinopril",
        "enalapril",
        "ramipril",
        "benazepril",
        "captopril",
        "fosinopril",
        "perindopril",
        "quinapril",
        "trandolapril",
        "losartan",
        "valsartan",
        "candesartan",
        "irbesartan",
        "olmesartan",
        "telmisartan",
        "azilsartan",
        "eprosartan",
    ]

    for agent in acei_arb_agents:
        finding = AceiKsparingChecker().check(
            _meds(f"{agent.title()} 10 mg daily", "Eplerenone 25 mg daily")
        )[0]
        assert finding.agent == agent
        assert finding.partner_agent == "eplerenone"


def test_all_potassium_sparing_panel_agents_participate() -> None:
    """Every supported potassium-sparing agent can produce a finding."""
    partners = ["spironolactone", "eplerenone", "amiloride", "triamterene"]

    for partner in partners:
        finding = AceiKsparingChecker().check(
            _meds("Losartan 50 mg daily", f"{partner.title()} 25 mg daily")
        )[0]
        assert finding.partner_agent == partner


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes do not match either medication panel."""
    checker = AceiKsparingChecker()

    assert checker.check(_meds("Lisinopriloid", "Spironolactonefree")) == []
    assert len(checker.check(_meds("Lisinopril 10 mg", "Spironolactone 25 mg"))) == 1


def test_acei_plus_arb_without_potassium_sparing_agent_is_out_of_scope() -> None:
    """Dual RAAS blockade belongs to its own control and does not trigger this one."""
    assert (
        AceiKsparingChecker().check(_meds("Lisinopril 20 mg daily", "Losartan 50 mg daily")) == []
    )


def test_duplicate_entries_do_not_duplicate_canonical_pairs() -> None:
    """Duplicate entries for the same agents yield one canonical pair."""
    findings = AceiKsparingChecker().check(
        _meds(
            "Losartan 50 mg daily",
            "Losartan 25 mg daily",
            "Amiloride 5 mg daily",
            "Amiloride 10 mg daily",
        )
    )

    assert len(findings) == 1


def test_findings_are_deterministic_across_input_order() -> None:
    """Multiple canonical pairs have stable medication/agent ordering."""
    names = [
        "Spironolactone 25 mg daily",
        "Losartan 50 mg daily",
        "Amiloride 5 mg daily",
        "Candesartan 8 mg daily",
    ]
    checker = AceiKsparingChecker()

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
    assert [(finding.agent, finding.partner_agent) for finding in forward] == [
        ("candesartan", "amiloride"),
        ("candesartan", "spironolactone"),
        ("losartan", "amiloride"),
        ("losartan", "spironolactone"),
    ]


def test_single_entry_is_not_treated_as_coprescription() -> None:
    """Two class names in one display string do not represent two prescriptions."""
    assert (
        AceiKsparingChecker().check(_meds("Lisinopril and spironolactone interaction note")) == []
    )


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(_meds("Enalapril 10 mg daily", "Triamterene 50 mg daily"))

    assert len(findings) == 1
    assert findings[0].agent == "enalapril"
    assert findings[0].partner_agent == "triamterene"
