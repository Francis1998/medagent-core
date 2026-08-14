"""Tests for the methotrexate + NSAID reduced-clearance checker."""

from __future__ import annotations

from medagent.models import Medication, MtxNsaidRisk, Severity
from medagent.safety import MtxNsaidChecker as ExportedChecker
from medagent.safety.mtx_nsaid_checker import MtxNsaidChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    """Methotrexate or an NSAID alone yields no finding."""
    checker = MtxNsaidChecker()

    assert checker.check(_meds("Methotrexate 15 mg weekly")) == []
    assert checker.check(_meds("Ibuprofen 400 mg TID PRN")) == []
    assert checker.check([]) == []


def test_flags_methotrexate_plus_ketorolac_critical() -> None:
    """Methotrexate + ketorolac yields a CRITICAL research-only finding."""
    findings = MtxNsaidChecker().check(
        _meds("Methotrexate 15 mg weekly", "Ketorolac 10 mg QID PRN")
    )

    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, MtxNsaidRisk)
    assert finding.agent == "methotrexate"
    assert finding.partner_agent == "ketorolac"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "clearance" in finding.rationale.lower()
    assert (
        "toxicity" in finding.rationale.lower() or "myelosuppression" in finding.rationale.lower()
    )


def test_ibuprofen_is_high_and_indomethacin_is_critical() -> None:
    """Severity separates standard panel NSAIDs from highest-risk partners."""
    checker = MtxNsaidChecker()

    ibuprofen = checker.check(_meds("Methotrexate 15 mg weekly", "Ibuprofen 400 mg TID"))[0]
    indomethacin = checker.check(_meds("Methotrexate 15 mg weekly", "Indomethacin 25 mg TID"))[0]

    assert ibuprofen.severity is Severity.HIGH
    assert indomethacin.severity is Severity.CRITICAL


def test_all_supported_nsaids_participate() -> None:
    """Every requested NSAID token can produce a finding."""
    for nsaid_agent in ["ibuprofen", "naproxen", "diclofenac", "indomethacin", "ketorolac"]:
        finding = MtxNsaidChecker().check(
            _meds("Methotrexate 15 mg weekly", f"{nsaid_agent.title()} 100 mg")
        )[0]
        assert finding.partner_agent == nsaid_agent


def test_neighboring_mtx_and_nsaid_controls_are_out_of_scope() -> None:
    """TMP-SMX and NSAIDs outside this focused list do not trigger."""
    checker = MtxNsaidChecker()

    assert checker.check(_meds("Methotrexate 15 mg weekly", "Bactrim DS BID")) == []
    assert checker.check(_meds("Methotrexate 15 mg weekly", "Celecoxib 100 mg BID")) == []
    assert checker.check(_meds("Lithium 300 mg BID", "Ibuprofen 400 mg TID")) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes do not match either medication panel."""
    checker = MtxNsaidChecker()

    assert checker.check(_meds("Methotrexateoid", "Ibuprofenoid")) == []
    assert len(checker.check(_meds("Methotrexate 15 mg", "Ibuprofen 400 mg"))) == 1


def test_duplicate_entries_do_not_duplicate_canonical_pairs() -> None:
    """Duplicate entries for the same agents yield one canonical pair."""
    findings = MtxNsaidChecker().check(
        _meds(
            "Methotrexate 10 mg weekly",
            "Methotrexate 15 mg weekly",
            "Naproxen 250 mg BID",
            "Naproxen 500 mg BID",
        )
    )

    assert len(findings) == 1


def test_findings_are_deterministic_across_input_order() -> None:
    """Multiple canonical pairs have stable severity and medication ordering."""
    names = [
        "Naproxen 250 mg BID",
        "Ketorolac 10 mg QID",
        "Methotrexate 15 mg weekly",
        "Ibuprofen 400 mg TID",
        "Indomethacin 25 mg TID",
        "Diclofenac 50 mg BID",
    ]
    checker = MtxNsaidChecker()

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
        ("indomethacin", Severity.CRITICAL),
        ("ketorolac", Severity.CRITICAL),
        ("diclofenac", Severity.HIGH),
        ("ibuprofen", Severity.HIGH),
        ("naproxen", Severity.HIGH),
    ]


def test_single_entry_is_not_treated_as_coprescription() -> None:
    """Two class names in one display string do not represent two prescriptions."""
    assert MtxNsaidChecker().check(_meds("Methotrexate and ibuprofen interaction note")) == []


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    finding = ExportedChecker().check(_meds("Methotrexate 15 mg weekly", "Diclofenac 50 mg BID"))[0]

    assert finding.agent == "methotrexate"
    assert finding.partner_agent == "diclofenac"
    assert finding.severity is Severity.HIGH
