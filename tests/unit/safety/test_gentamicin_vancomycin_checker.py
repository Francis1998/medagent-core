"""Tests for the Aminoglycoside + Vancomycin safety checker."""

from medagent.models import GentamicinVancomycinRisk, Medication, Severity
from medagent.safety import GentamicinVancomycinChecker as ExportedChecker
from medagent.safety.gentamicin_vancomycin_checker import GentamicinVancomycinChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = GentamicinVancomycinChecker()
    assert checker.check(_meds("gentamicin dose")) == []
    assert checker.check(_meds("vancomycin dose")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    checker = GentamicinVancomycinChecker()
    finding = checker.check(_meds("gentamicin dose", "vancomycin dose"))[0]
    assert isinstance(finding, GentamicinVancomycinRisk)
    assert finding.agent == "gentamicin"
    assert finding.partner_agent == "vancomycin"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale


def test_all_supported_agents_participate() -> None:
    checker = GentamicinVancomycinChecker()
    for primary_agent in ["gentamicin", "tobramycin", "amikacin", "garamycin", "tobi"]:
        finding = checker.check(_meds(f"{primary_agent} dose", "vancomycin dose"))[0]
        assert finding.agent == primary_agent
    for partner_agent in ["vancomycin", "vancocin"]:
        finding = checker.check(_meds("gentamicin dose", f"{partner_agent} dose"))[0]
        assert finding.partner_agent == partner_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = GentamicinVancomycinChecker()
    assert checker.check(_meds("gentamicinlike", "vancomycinlike")) == []
    assert len(checker.check(_meds("gentamicin", "vancomycin"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["vancomycin dose", "gentamicin dose", "tobramycin dose"]
    checker = GentamicinVancomycinChecker()
    forward = checker.check(_meds(*names))
    reverse = checker.check(_meds(*reversed(names)))
    assert [(i.agent, i.partner_agent) for i in forward] == [
        (i.agent, i.partner_agent) for i in reverse
    ]
    assert (
        len(
            checker.check(
                _meds(
                    "gentamicin a",
                    "gentamicin b",
                    "vancomycin a",
                    "vancomycin b",
                )
            )
        )
        == 1
    )


def test_export_alias_matches() -> None:
    assert ExportedChecker is GentamicinVancomycinChecker


def test_rationale_mentions_research_only() -> None:
    finding = GentamicinVancomycinChecker().check(_meds("gentamicin", "vancomycin"))[0]
    assert finding.rationale.startswith("RESEARCH USE ONLY")


def test_severity_ordering_stable() -> None:
    findings = GentamicinVancomycinChecker().check(_meds("gentamicin", "vancomycin"))
    assert findings
    ranks = {Severity.HIGH: 3, Severity.CRITICAL: 4}
    assert ranks[findings[0].severity] >= 3
