"""Tests for the lithium + ACE inhibitor/ARB safety checker."""

from medagent.models import LithiumAceiRisk, Medication, Severity
from medagent.safety import LithiumAceiChecker as ExportedChecker
from medagent.safety.lithium_acei_checker import LithiumAceiChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = LithiumAceiChecker()
    assert checker.check(_meds("Lithium 300 mg BID")) == []
    assert checker.check(_meds("Lisinopril 10 mg daily")) == []
    assert checker.check([]) == []


def test_flags_lithium_plus_lisinopril_high() -> None:
    finding = LithiumAceiChecker().check(_meds("Lithium 300 mg BID", "Lisinopril 10 mg daily"))[0]
    assert isinstance(finding, LithiumAceiRisk)
    assert finding.agent == "lithium"
    assert finding.partner_agent == "lisinopril"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "clearance" in finding.rationale.lower()


def test_lithium_brands_and_all_supported_raas_agents_participate() -> None:
    for lithium_agent in ["lithium", "lithobid", "eskalith"]:
        finding = LithiumAceiChecker().check(
            _meds(f"{lithium_agent.title()} 300 mg", "Enalapril 10 mg")
        )[0]
        assert finding.agent == lithium_agent

    for partner in [
        "lisinopril",
        "enalapril",
        "ramipril",
        "benazepril",
        "quinapril",
        "captopril",
        "fosinopril",
        "perindopril",
        "trandolapril",
        "moexipril",
        "losartan",
        "valsartan",
        "olmesartan",
        "candesartan",
        "irbesartan",
        "telmisartan",
        "azilsartan",
    ]:
        finding = LithiumAceiChecker().check(_meds("Lithium 300 mg", f"{partner.title()} 10 mg"))[0]
        assert finding.partner_agent == partner
        assert finding.severity is Severity.HIGH


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = LithiumAceiChecker()
    assert checker.check(_meds("Lithiumlike supplement", "Lisinopriloid")) == []
    assert len(checker.check(_meds("Lithium", "Losartan"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Valsartan 80 mg", "Lithium 300 mg", "Lisinopril 10 mg"]
    forward = LithiumAceiChecker().check(_meds(*names))
    reverse = LithiumAceiChecker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent) for item in forward] == [
        (item.agent, item.partner_agent) for item in reverse
    ]
    assert [item.partner_agent for item in forward] == ["lisinopril", "valsartan"]
    assert (
        len(
            LithiumAceiChecker().check(
                _meds("Lithium", "Lithium 300 mg", "Losartan", "Losartan 50 mg")
            )
        )
        == 1
    )


def test_single_entry_is_not_coprescription() -> None:
    assert LithiumAceiChecker().check(_meds("Lithium and lisinopril warning")) == []


def test_checker_is_exported_from_safety_package() -> None:
    finding = ExportedChecker().check(_meds("Lithobid", "Ramipril"))[0]
    assert finding.partner_agent == "ramipril"
