"""Tests for the metformin + iodinated contrast media lactic acidosis checker."""

from medagent.models import Medication, MetforminContrastRisk, Severity
from medagent.safety import MetforminContrastChecker as ExportedChecker
from medagent.safety.metformin_contrast_checker import MetforminContrastChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = MetforminContrastChecker()
    assert checker.check(_meds("Metformin 500 mg")) == []
    assert checker.check(_meds("Iohexol injection")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = MetforminContrastChecker().check(_meds("Metformin 500 mg", "Iohexol injection"))[0]

    assert isinstance(finding, MetforminContrastRisk)
    assert finding.agent == "metformin"
    assert finding.partner_agent == "iohexol"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "lactic acidosis" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["metformin", "glucophage", "fortamet", "glumetza", "riomet"]:
        finding = MetforminContrastChecker().check(
            _meds(f"{primary_agent} dose", "Iodixanol 300 mg/mL")
        )[0]
        assert finding.agent == primary_agent

    for partner_agent, label in [
        ("contrast", "IV Contrast bolus"),
        ("contrast-media", "Contrast-Media administration"),
        ("iohexol", "Iohexol 300 mg/mL"),
        ("iodixanol", "Iodixanol 320 mg/mL"),
        ("iopamidol", "Iopamidol 370 mg/mL"),
    ]:
        finding = MetforminContrastChecker().check(_meds("Metformin 500 mg", label))[0]
        assert finding.partner_agent == partner_agent
        assert finding.severity is Severity.HIGH


def test_related_but_out_of_scope_agents_do_not_flag() -> None:
    checker = MetforminContrastChecker()
    for agent in ["Glipizide", "Insulin Glargine", "Barium Sulfate", "Gadolinium"]:
        assert checker.check(_meds("Metformin 500 mg", agent)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = MetforminContrastChecker()
    assert checker.check(_meds("Metforminlike", "Contrastfree")) == []
    assert len(checker.check(_meds("Glucophage", "Iopamidol"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Iohexol 300 mg/mL", "Metformin 500 mg", "Iodixanol 300 mg/mL"]
    forward = MetforminContrastChecker().check(_meds(*names))
    reverse = MetforminContrastChecker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert [item.partner_agent for item in forward] == ["iodixanol", "iohexol"]
    assert (
        len(
            MetforminContrastChecker().check(
                _meds(
                    "Metformin 500 mg",
                    "Metformin 500 mg",
                    "Iohexol 300 mg/mL",
                    "Iohexol 300 mg/mL",
                )
            )
        )
        == 1
    )


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        MetforminContrastChecker().check(_meds("Metformin and contrast interaction warning")) == []
    )
    finding = ExportedChecker().check(_meds("Fortamet", "Iopamidol"))[0]
    assert finding.severity is Severity.HIGH
