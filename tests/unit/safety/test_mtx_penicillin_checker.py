"""Tests for the methotrexate + penicillin toxicity checker."""

from medagent.models import Medication, MtxPenicillinRisk, Severity
from medagent.safety import MtxPenicillinChecker as ExportedChecker
from medagent.safety.mtx_penicillin_checker import MtxPenicillinChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = MtxPenicillinChecker()
    assert checker.check(_meds("Methotrexate 15 mg weekly")) == []
    assert checker.check(_meds("Amoxicillin 500 mg")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = MtxPenicillinChecker().check(
        _meds("Methotrexate 15 mg weekly", "Amoxicillin 500 mg")
    )[0]

    assert isinstance(finding, MtxPenicillinRisk)
    assert finding.agent == "methotrexate"
    assert finding.partner_agent == "amoxicillin"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "reduce renal methotrexate clearance" in finding.rationale


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["methotrexate", "mtx"]:
        finding = MtxPenicillinChecker().check(
            _meds(f"{primary_agent} dose", "Amoxicillin 500 mg")
        )[0]
        assert finding.agent == primary_agent

    for partner_agent in ["penicillin", "penicillin-v", "pen-vk", "amoxicillin", "ampicillin"]:
        finding = MtxPenicillinChecker().check(
            _meds("Methotrexate 15 mg weekly", f"{partner_agent} dose")
        )[0]
        assert finding.partner_agent == partner_agent
        assert finding.severity is Severity.HIGH


def test_related_but_out_of_scope_agents_do_not_flag() -> None:
    checker = MtxPenicillinChecker()
    for agent in ["Ibuprofen", "Bactrim", "Naproxen"]:
        assert checker.check(_meds("Methotrexate 15 mg weekly", agent)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = MtxPenicillinChecker()
    assert checker.check(_meds("Methotrexatelike", "Penicillinoid")) == []
    assert len(checker.check(_meds("MTX", "Pen-VK"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Penicillin 500 mg", "Methotrexate 15 mg weekly", "Amoxicillin 500 mg"]
    forward = MtxPenicillinChecker().check(_meds(*names))
    reverse = MtxPenicillinChecker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert [item.partner_agent for item in forward] == ["amoxicillin", "penicillin"]
    assert (
        len(
            MtxPenicillinChecker().check(
                _meds(
                    "Methotrexate 15 mg weekly",
                    "Methotrexate 15 mg weekly",
                    "Amoxicillin 500 mg",
                    "Amoxicillin 500 mg",
                )
            )
        )
        == 1
    )


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert MtxPenicillinChecker().check(_meds("MTX and Pen-VK interaction warning")) == []
    finding = ExportedChecker().check(_meds("MTX", "Pen-VK"))[0]
    assert finding.severity is Severity.HIGH
