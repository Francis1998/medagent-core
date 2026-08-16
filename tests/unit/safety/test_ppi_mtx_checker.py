"""Tests for the PPI + methotrexate toxicity safety checker."""

from medagent.models import Medication, PpiMtxRisk, Severity
from medagent.safety import PpiMtxChecker as ExportedChecker
from medagent.safety.ppi_mtx_checker import PpiMtxChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = PpiMtxChecker()
    assert checker.check(_meds("Methotrexate 15 mg weekly")) == []
    assert checker.check(_meds("Omeprazole 20 mg daily")) == []
    assert checker.check([]) == []


def test_flags_methotrexate_plus_omeprazole_high() -> None:
    finding = PpiMtxChecker().check(_meds("Methotrexate 15 mg weekly", "Omeprazole 20 mg daily"))[0]
    assert isinstance(finding, PpiMtxRisk)
    assert finding.agent == "methotrexate"
    assert finding.partner_agent == "omeprazole"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "clearance" in finding.rationale.lower()


def test_all_supported_ppis_participate() -> None:
    for ppi in [
        "omeprazole",
        "esomeprazole",
        "pantoprazole",
        "lansoprazole",
        "rabeprazole",
    ]:
        finding = PpiMtxChecker().check(_meds("Methotrexate 10 mg weekly", f"{ppi.title()} 20 mg"))[
            0
        ]
        assert finding.partner_agent == ppi
        assert finding.severity is Severity.HIGH


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = PpiMtxChecker()
    assert checker.check(_meds("Pseudomethotrexate", "Omeprazoleish")) == []
    assert len(checker.check(_meds("Methotrexate", "Pantoprazole"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Pantoprazole 40 mg", "Methotrexate 10 mg", "Omeprazole 20 mg"]
    forward = PpiMtxChecker().check(_meds(*names))
    reverse = PpiMtxChecker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent) for item in forward] == [
        (item.agent, item.partner_agent) for item in reverse
    ]
    assert [item.partner_agent for item in forward] == ["omeprazole", "pantoprazole"]
    assert (
        len(
            PpiMtxChecker().check(
                _meds("Methotrexate", "Methotrexate 10 mg", "Omeprazole", "Omeprazole 20 mg")
            )
        )
        == 1
    )


def test_single_entry_is_not_coprescription() -> None:
    assert PpiMtxChecker().check(_meds("Methotrexate and omeprazole interaction note")) == []


def test_checker_is_exported_from_safety_package() -> None:
    finding = ExportedChecker().check(_meds("Methotrexate", "Rabeprazole"))[0]
    assert finding.partner_agent == "rabeprazole"
