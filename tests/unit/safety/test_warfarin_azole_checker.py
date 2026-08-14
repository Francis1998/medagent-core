"""Tests for the warfarin + systemic azole antifungal checker."""

from __future__ import annotations

from medagent.models import Medication, Severity, WarfarinAzoleRisk
from medagent.safety import WarfarinAzoleChecker as ExportedChecker
from medagent.safety.warfarin_azole_checker import WarfarinAzoleChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    """Warfarin or an azole alone yields no finding."""
    checker = WarfarinAzoleChecker()

    assert checker.check(_meds("Warfarin 5 mg daily")) == []
    assert checker.check(_meds("Fluconazole 200 mg daily")) == []
    assert checker.check([]) == []


def test_flags_warfarin_plus_fluconazole_critical() -> None:
    """Warfarin + fluconazole yields a CRITICAL research-only finding."""
    findings = WarfarinAzoleChecker().check(
        _meds("Warfarin 5 mg daily", "Fluconazole 200 mg daily")
    )

    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, WarfarinAzoleRisk)
    assert finding.agent == "warfarin"
    assert finding.partner_agent == "fluconazole"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "CYP2C9" in finding.rationale
    assert "INR" in finding.rationale


def test_coumadin_plus_ketoconazole_is_high() -> None:
    """Coumadin + ketoconazole yields HIGH severity."""
    finding = WarfarinAzoleChecker().check(
        _meds("Coumadin 2.5 mg daily", "Ketoconazole 200 mg daily")
    )[0]

    assert finding.agent == "coumadin"
    assert finding.partner_agent == "ketoconazole"
    assert finding.severity is Severity.HIGH


def test_all_supported_agents_participate() -> None:
    """Every supported warfarin and systemic azole token can produce a finding."""
    for warfarin_agent in ["warfarin", "coumadin"]:
        finding = WarfarinAzoleChecker().check(
            _meds(f"{warfarin_agent.title()} 5 mg", "Fluconazole 200 mg")
        )[0]
        assert finding.agent == warfarin_agent

    for azole_agent in ["fluconazole", "ketoconazole", "itraconazole", "voriconazole"]:
        finding = WarfarinAzoleChecker().check(
            _meds("Warfarin 5 mg", f"{azole_agent.title()} 200 mg")
        )[0]
        assert finding.partner_agent == azole_agent


def test_critical_and_high_azole_severity_tiers() -> None:
    """Fluconazole/voriconazole are CRITICAL; other panel azoles are HIGH."""
    checker = WarfarinAzoleChecker()

    for agent in ["fluconazole", "voriconazole"]:
        assert checker.check(_meds("Warfarin 5 mg", agent))[0].severity is Severity.CRITICAL
    for agent in ["ketoconazole", "itraconazole"]:
        assert checker.check(_meds("Warfarin 5 mg", agent))[0].severity is Severity.HIGH


def test_topical_clotrimazole_is_out_of_scope() -> None:
    """Clotrimazole is intentionally excluded from the systemic azole panel."""
    assert (
        WarfarinAzoleChecker().check(_meds("Warfarin 5 mg daily", "Clotrimazole 1% topical cream"))
        == []
    )


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes do not match either medication panel."""
    checker = WarfarinAzoleChecker()

    assert checker.check(_meds("Warfarinoid", "Fluconazoleish")) == []
    assert len(checker.check(_meds("Warfarin 5 mg", "Fluconazole 200 mg"))) == 1


def test_duplicate_entries_do_not_duplicate_canonical_pairs() -> None:
    """Duplicate entries for the same agents yield one canonical pair."""
    findings = WarfarinAzoleChecker().check(
        _meds(
            "Warfarin 2.5 mg daily",
            "Warfarin 5 mg daily",
            "Fluconazole 100 mg daily",
            "Fluconazole 200 mg daily",
        )
    )

    assert len(findings) == 1


def test_findings_are_deterministic_across_input_order() -> None:
    """Multiple canonical pairs have stable severity and medication ordering."""
    names = [
        "Ketoconazole 200 mg daily",
        "Voriconazole 200 mg BID",
        "Warfarin 5 mg daily",
        "Fluconazole 100 mg daily",
        "Itraconazole 200 mg daily",
    ]
    checker = WarfarinAzoleChecker()

    forward = checker.check(_meds(*names))
    reverse = checker.check(_meds(*reversed(names)))

    forward_values = [
        (
            finding.medication,
            finding.partner_medication,
            finding.agent,
            finding.partner_agent,
            finding.severity,
        )
        for finding in forward
    ]
    reverse_values = [
        (
            finding.medication,
            finding.partner_medication,
            finding.agent,
            finding.partner_agent,
            finding.severity,
        )
        for finding in reverse
    ]
    assert forward_values == reverse_values
    assert [(finding.partner_agent, finding.severity) for finding in forward] == [
        ("fluconazole", Severity.CRITICAL),
        ("voriconazole", Severity.CRITICAL),
        ("itraconazole", Severity.HIGH),
        ("ketoconazole", Severity.HIGH),
    ]


def test_single_entry_is_not_treated_as_coprescription() -> None:
    """Two class names in one display string do not represent two prescriptions."""
    assert WarfarinAzoleChecker().check(_meds("Warfarin and fluconazole interaction note")) == []


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    finding = ExportedChecker().check(_meds("Coumadin 2.5 mg daily", "Voriconazole 200 mg BID"))[0]

    assert finding.agent == "coumadin"
    assert finding.partner_agent == "voriconazole"
    assert finding.severity is Severity.CRITICAL
