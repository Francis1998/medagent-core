"""Tests for the warfarin + TMP-SMX INR elevation / bleed-risk checker."""

from medagent.models import Medication, Severity, WarfarinTmpsmxRisk
from medagent.safety import WarfarinTmpsmxChecker as ExportedChecker
from medagent.safety.warfarin_tmpsmx_checker import WarfarinTmpsmxChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = WarfarinTmpsmxChecker()
    assert checker.check(_meds("Warfarin 5 mg daily")) == []
    assert checker.check(_meds("Bactrim DS BID")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_critical_severity() -> None:
    finding = WarfarinTmpsmxChecker().check(_meds("Warfarin 5 mg daily", "Bactrim DS BID"))[0]

    assert isinstance(finding, WarfarinTmpsmxRisk)
    assert finding.agent == "warfarin"
    assert finding.partner_agent == "bactrim"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "inr" in finding.rationale.lower() or "bleed" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["warfarin", "coumadin", "jantoven"]:
        finding = WarfarinTmpsmxChecker().check(_meds(f"{primary_agent} dose", "Bactrim DS"))[0]
        assert finding.agent == primary_agent

    for partner_agent in [
        "trimethoprim",
        "sulfamethoxazole",
        "bactrim",
        "septra",
        "cotrimoxazole",
        "tmp-smx",
        "trimethoprim-sulfamethoxazole",
    ]:
        finding = WarfarinTmpsmxChecker().check(_meds("Warfarin 5 mg", f"{partner_agent} tablet"))[
            0
        ]
        assert finding.partner_agent == partner_agent
        assert finding.severity is Severity.CRITICAL


def test_related_but_out_of_scope_agents_do_not_flag() -> None:
    checker = WarfarinTmpsmxChecker()
    # Distinct from mtx_tmpsmx and fluoroquinolone_warfarin
    for agent in ["Methotrexate", "Ciprofloxacin", "Levofloxacin", "Metronidazole"]:
        assert checker.check(_meds("Warfarin 5 mg", agent)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = WarfarinTmpsmxChecker()
    assert checker.check(_meds("Warfarinlike", "Bactrimfree")) == []
    assert len(checker.check(_meds("Warfarin", "Bactrim"))) == 1
    assert len(checker.check(_meds("Coumadin", "TMP-SMX"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Bactrim DS", "Warfarin 5 mg", "Septra DS"]
    forward = WarfarinTmpsmxChecker().check(_meds(*names))
    reverse = WarfarinTmpsmxChecker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert (
        len(
            WarfarinTmpsmxChecker().check(
                _meds(
                    "Warfarin 5 mg",
                    "Warfarin 2 mg",
                    "Bactrim DS",
                    "Bactrim SS",
                )
            )
        )
        == 1
    )


def test_findings_sorted_deterministically() -> None:
    findings = WarfarinTmpsmxChecker().check(_meds("Warfarin 5 mg", "Septra DS", "Bactrim DS"))
    assert [finding.severity for finding in findings] == [Severity.CRITICAL, Severity.CRITICAL]
    assert [finding.partner_agent for finding in findings] == ["bactrim", "septra"]


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert WarfarinTmpsmxChecker().check(_meds("Warfarin and Bactrim interaction warning")) == []
    finding = ExportedChecker().check(_meds("Jantoven 5 mg", "Septra DS"))[0]
    assert finding.agent == "jantoven"
    assert finding.partner_agent == "septra"
    assert finding.severity is Severity.CRITICAL
