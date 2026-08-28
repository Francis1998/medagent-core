"""Tests for the methotrexate + trimethoprim / TMP-SMX antifolate synergy checker."""

from medagent.models import Medication, MethotrexateTrimethoprimRisk, Severity
from medagent.safety import MethotrexateTrimethoprimChecker as ExportedChecker
from medagent.safety.methotrexate_trimethoprim_checker import MethotrexateTrimethoprimChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = MethotrexateTrimethoprimChecker()
    assert checker.check(_meds("Methotrexate 15 mg weekly")) == []
    assert checker.check(_meds("Bactrim DS BID")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = MethotrexateTrimethoprimChecker().check(
        _meds("Methotrexate 15 mg weekly", "Bactrim DS BID")
    )[0]

    assert isinstance(finding, MethotrexateTrimethoprimRisk)
    assert finding.agent == "methotrexate"
    assert finding.partner_agent == "bactrim"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "antifolate" in finding.rationale.lower() or "pancytopenia" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["methotrexate", "trexall", "otrexup", "rasuvo", "xatmep"]:
        finding = MethotrexateTrimethoprimChecker().check(
            _meds(f"{primary_agent} dose", "Bactrim DS")
        )[0]
        assert finding.agent == primary_agent

    for partner_agent, label in [
        ("trimethoprim", "Trimethoprim 100 mg"),
        ("tmp-smx", "TMP-SMX DS"),
        ("bactrim", "Bactrim DS"),
        ("septra", "Septra DS"),
        ("co-trimoxazole", "Co-trimoxazole DS"),
        ("trimethoprim-sulfamethoxazole", "Trimethoprim-sulfamethoxazole DS"),
    ]:
        finding = MethotrexateTrimethoprimChecker().check(_meds("Methotrexate 15 mg", label))[0]
        assert finding.partner_agent == partner_agent
        assert finding.severity is Severity.CRITICAL


def test_related_but_out_of_scope_agents_do_not_flag() -> None:
    checker = MethotrexateTrimethoprimChecker()
    # Distinct from warfarin + TMP-SMX and methotrexate + NSAID
    for agent in ["Warfarin", "Ibuprofen", "Sulfadiazine", "Nitrofurantoin"]:
        assert checker.check(_meds("Methotrexate 15 mg", agent)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = MethotrexateTrimethoprimChecker()
    assert checker.check(_meds("Methotrexatelike", "Bactrimfree")) == []
    assert len(checker.check(_meds("Methotrexate", "Bactrim"))) == 1
    assert len(checker.check(_meds("Trexall", "TMP-SMX"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Bactrim DS", "Methotrexate 15 mg", "Septra DS"]
    forward = MethotrexateTrimethoprimChecker().check(_meds(*names))
    reverse = MethotrexateTrimethoprimChecker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert (
        len(
            MethotrexateTrimethoprimChecker().check(
                _meds(
                    "Methotrexate 15 mg",
                    "Methotrexate 10 mg",
                    "Bactrim DS",
                    "Bactrim SS",
                )
            )
        )
        == 1
    )


def test_findings_sorted_deterministically_by_partner() -> None:
    findings = MethotrexateTrimethoprimChecker().check(
        _meds("Methotrexate 15 mg", "Septra DS", "Bactrim DS")
    )
    assert all(finding.severity is Severity.CRITICAL for finding in findings)
    assert [finding.partner_agent for finding in findings] == ["bactrim", "septra"]


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        MethotrexateTrimethoprimChecker().check(
            _meds("Methotrexate and Bactrim interaction warning")
        )
        == []
    )
    finding = ExportedChecker().check(_meds("Xatmep 2.5 mg", "Co-trimoxazole DS"))[0]
    assert finding.agent == "xatmep"
    assert finding.partner_agent == "co-trimoxazole"
    assert finding.severity is Severity.CRITICAL
