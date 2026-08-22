"""Tests for the codeine + CYP2D6 inhibitor checker."""

from medagent.models import CodeineCyp2d6Risk, Medication, Severity
from medagent.safety import CodeineCyp2d6Checker as ExportedChecker
from medagent.safety.codeine_cyp2d6_checker import CodeineCyp2d6Checker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = CodeineCyp2d6Checker()
    assert checker.check(_meds("Codeine 30 mg")) == []
    assert checker.check(_meds("Fluoxetine 20 mg")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = CodeineCyp2d6Checker().check(_meds("Codeine 30 mg", "Fluoxetine 20 mg"))[0]

    assert isinstance(finding, CodeineCyp2d6Risk)
    assert finding.agent == "codeine"
    assert finding.partner_agent == "fluoxetine"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "CYP2D6" in finding.rationale


def test_all_supported_agents_participate() -> None:
    for primary_agent, label in [
        ("codeine", "Codeine 30 mg"),
        ("tylenol-with-codeine", "Tylenol with Codeine #3"),
    ]:
        finding = CodeineCyp2d6Checker().check(_meds(label, "Paroxetine 20 mg"))[0]
        assert finding.agent == primary_agent

    for partner_agent in ["fluoxetine", "paroxetine", "bupropion", "quinidine", "terbinafine"]:
        finding = CodeineCyp2d6Checker().check(_meds("Codeine 30 mg", f"{partner_agent} dose"))[0]
        assert finding.partner_agent == partner_agent
        assert finding.severity is Severity.HIGH


def test_related_but_out_of_scope_agents_do_not_flag() -> None:
    checker = CodeineCyp2d6Checker()
    for agent in ["Tramadol", "Oxycodone", "Sertraline", "Duloxetine"]:
        assert checker.check(_meds("Codeine 30 mg", agent)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = CodeineCyp2d6Checker()
    assert checker.check(_meds("Codeinelike", "Fluoxetinefree")) == []
    assert len(checker.check(_meds("Tylenol-with-Codeine", "Bupropion"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Paroxetine 20 mg", "Codeine 30 mg", "Fluoxetine 20 mg"]
    forward = CodeineCyp2d6Checker().check(_meds(*names))
    reverse = CodeineCyp2d6Checker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert [item.partner_agent for item in forward] == ["fluoxetine", "paroxetine"]
    assert (
        len(
            CodeineCyp2d6Checker().check(
                _meds(
                    "Codeine 30 mg",
                    "Codeine 30 mg",
                    "Fluoxetine 20 mg",
                    "Fluoxetine 20 mg",
                )
            )
        )
        == 1
    )


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert CodeineCyp2d6Checker().check(_meds("Codeine and Fluoxetine interaction warning")) == []
    finding = ExportedChecker().check(_meds("Codeine", "Quinidine"))[0]
    assert finding.severity is Severity.HIGH
