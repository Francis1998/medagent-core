"""Tests for the ACEI/ARB + potassium supplement hyperkalemia checker."""

from medagent.models import AceiPotassiumRisk, Medication, Severity
from medagent.safety import AceiPotassiumChecker as ExportedChecker
from medagent.safety.acei_potassium_checker import AceiPotassiumChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = AceiPotassiumChecker()
    assert checker.check(_meds("Lisinopril 10 mg")) == []
    assert checker.check(_meds("Potassium Chloride 20 mEq")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = AceiPotassiumChecker().check(_meds("Lisinopril 10 mg", "Potassium Chloride 20 mEq"))[
        0
    ]

    assert isinstance(finding, AceiPotassiumRisk)
    assert finding.agent == "lisinopril"
    assert finding.partner_agent == "potassium-chloride"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "hyperkalemia" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["lisinopril", "enalapril", "ramipril", "losartan", "valsartan"]:
        finding = AceiPotassiumChecker().check(_meds(f"{primary_agent} dose", "KCl 20 mEq"))[0]
        assert finding.agent == primary_agent

    for partner_agent, label in [
        ("potassium", "Potassium 20 mEq"),
        ("kcl", "KCl 20 mEq"),
        ("klor-con", "Klor-Con 10 mEq"),
        ("potassium-chloride", "Potassium Chloride 20 mEq"),
    ]:
        finding = AceiPotassiumChecker().check(_meds("Lisinopril 10 mg", label))[0]
        assert finding.partner_agent == partner_agent
        assert finding.severity is Severity.HIGH


def test_related_but_out_of_scope_agents_do_not_flag() -> None:
    checker = AceiPotassiumChecker()
    # Distinct from ACEI + K-sparing (#3.60) and ACEI + TMP (#3.63)
    for agent in ["Spironolactone", "Eplerenone", "Trimethoprim", "Bactrim"]:
        assert checker.check(_meds("Lisinopril 10 mg", agent)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = AceiPotassiumChecker()
    assert checker.check(_meds("Lisinoprillike", "Potassiumfree")) == []
    assert len(checker.check(_meds("Losartan", "Klor-Con"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["KCl 20 mEq", "Lisinopril 10 mg", "Klor-Con 10 mEq"]
    forward = AceiPotassiumChecker().check(_meds(*names))
    reverse = AceiPotassiumChecker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert [item.partner_agent for item in forward] == ["kcl", "klor-con"]
    assert (
        len(
            AceiPotassiumChecker().check(
                _meds(
                    "Lisinopril 10 mg",
                    "Lisinopril 10 mg",
                    "Potassium 20 mEq",
                    "Potassium 20 mEq",
                )
            )
        )
        == 1
    )


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert AceiPotassiumChecker().check(_meds("Lisinopril and Potassium interaction warning")) == []
    finding = ExportedChecker().check(_meds("Valsartan", "KCl"))[0]
    assert finding.severity is Severity.HIGH
