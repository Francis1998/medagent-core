"""Tests for the methotrexate + NSAID reduced-clearance toxicity checker."""

from medagent.models import Medication, MethotrexateNsaidRisk, Severity
from medagent.safety import MethotrexateNsaidChecker as ExportedChecker
from medagent.safety.methotrexate_nsaid_checker import MethotrexateNsaidChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = MethotrexateNsaidChecker()
    assert checker.check(_meds("Methotrexate 15 mg weekly")) == []
    assert checker.check(_meds("Ibuprofen 600 mg TID")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = MethotrexateNsaidChecker().check(
        _meds("Methotrexate 15 mg weekly", "Ketorolac 10 mg q6h")
    )[0]

    assert isinstance(finding, MethotrexateNsaidRisk)
    assert finding.agent == "methotrexate"
    assert finding.partner_agent == "ketorolac"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "clearance" in finding.rationale.lower() or "toxicity" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["methotrexate", "trexall", "otrexup", "rasuvo", "xatmep"]:
        finding = MethotrexateNsaidChecker().check(
            _meds(f"{primary_agent} dose", "Ibuprofen 400 mg")
        )[0]
        assert finding.agent == primary_agent

    for partner_agent, label, severity in [
        ("ibuprofen", "Ibuprofen 400 mg", Severity.HIGH),
        ("naproxen", "Naproxen 500 mg", Severity.HIGH),
        ("diclofenac", "Diclofenac 50 mg", Severity.HIGH),
        ("ketorolac", "Ketorolac 10 mg", Severity.CRITICAL),
        ("indomethacin", "Indomethacin 25 mg", Severity.HIGH),
        ("meloxicam", "Meloxicam 15 mg", Severity.HIGH),
        ("celecoxib", "Celecoxib 200 mg", Severity.HIGH),
        ("nsaid", "NSAID as needed", Severity.HIGH),
    ]:
        finding = MethotrexateNsaidChecker().check(_meds("Methotrexate 15 mg", label))[0]
        assert finding.partner_agent == partner_agent
        assert finding.severity is severity


def test_related_but_out_of_scope_agents_do_not_flag() -> None:
    checker = MethotrexateNsaidChecker()
    # Distinct from methotrexate + TMP-SMX and warfarin + NSAID
    for agent in ["Bactrim", "Warfarin", "Acetaminophen", "Aspirin"]:
        assert checker.check(_meds("Methotrexate 15 mg", agent)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = MethotrexateNsaidChecker()
    assert checker.check(_meds("Methotrexatelike", "Ibuprofenfree")) == []
    assert len(checker.check(_meds("Methotrexate", "Ibuprofen"))) == 1
    assert len(checker.check(_meds("Trexall", "Ketorolac"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Ibuprofen 400 mg", "Methotrexate 15 mg", "Naproxen 500 mg"]
    forward = MethotrexateNsaidChecker().check(_meds(*names))
    reverse = MethotrexateNsaidChecker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert (
        len(
            MethotrexateNsaidChecker().check(
                _meds(
                    "Methotrexate 15 mg",
                    "Methotrexate 10 mg",
                    "Ibuprofen 400 mg",
                    "Ibuprofen 200 mg",
                )
            )
        )
        == 1
    )


def test_findings_sorted_by_severity_first() -> None:
    findings = MethotrexateNsaidChecker().check(
        _meds("Methotrexate 15 mg", "Ibuprofen 400 mg", "Ketorolac 10 mg")
    )
    assert [finding.severity for finding in findings] == [Severity.CRITICAL, Severity.HIGH]
    assert findings[0].partner_agent == "ketorolac"
    assert findings[1].partner_agent == "ibuprofen"


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        MethotrexateNsaidChecker().check(_meds("Methotrexate and ibuprofen interaction warning"))
        == []
    )
    finding = ExportedChecker().check(_meds("Rasuvo 15 mg", "Ketorolac 10 mg"))[0]
    assert finding.agent == "rasuvo"
    assert finding.partner_agent == "ketorolac"
    assert finding.severity is Severity.CRITICAL
