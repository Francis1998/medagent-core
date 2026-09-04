"""Tests for the Sofosbuvir + Amiodarone Bradycardia Risk safety checker."""

from medagent.models import Medication, Severity, SofosbuvirAmiodaroneRisk
from medagent.safety import SofosbuvirAmiodaroneChecker as ExportedChecker
from medagent.safety.sofosbuvir_amiodarone_checker import SofosbuvirAmiodaroneChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = SofosbuvirAmiodaroneChecker()
    assert checker.check(_meds("sofosbuvir dose")) == []
    assert checker.check(_meds("amiodarone dose")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    checker = SofosbuvirAmiodaroneChecker()
    finding = checker.check(_meds("sofosbuvir dose", "amiodarone dose"))[0]
    assert isinstance(finding, SofosbuvirAmiodaroneRisk)
    assert finding.agent == "sofosbuvir"
    assert finding.partner_agent == "amiodarone"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale


def test_all_supported_agents_participate() -> None:
    checker = SofosbuvirAmiodaroneChecker()
    for primary_agent in ["sofosbuvir", "sovaldi", "harvoni", "epclusa"]:
        finding = checker.check(_meds(f"{primary_agent} dose", "amiodarone dose"))[0]
        assert finding.agent == primary_agent
    for partner_agent in ["amiodarone", "cordarone", "pacerone"]:
        finding = checker.check(_meds("sofosbuvir dose", f"{partner_agent} dose"))[0]
        assert finding.partner_agent == partner_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = SofosbuvirAmiodaroneChecker()
    assert checker.check(_meds("sofosbuvirlike", "amiodaronelike")) == []
    assert len(checker.check(_meds("sofosbuvir", "amiodarone"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["amiodarone dose", "sofosbuvir dose"]
    checker = SofosbuvirAmiodaroneChecker()
    forward = checker.check(_meds(*names))
    reverse = checker.check(_meds(*reversed(names)))
    assert [(i.agent, i.partner_agent) for i in forward] == [
        (i.agent, i.partner_agent) for i in reverse
    ]
    assert (
        len(
            checker.check(
                _meds(
                    "sofosbuvir a",
                    "sofosbuvir b",
                    "amiodarone a",
                    "amiodarone b",
                )
            )
        )
        == 1
    )


def test_export_alias_matches() -> None:
    assert ExportedChecker is SofosbuvirAmiodaroneChecker


def test_rationale_mentions_research_only() -> None:
    finding = SofosbuvirAmiodaroneChecker().check(_meds("sofosbuvir", "amiodarone"))[0]
    assert finding.rationale.startswith("RESEARCH USE ONLY")


def test_severity_ordering_stable() -> None:
    findings = SofosbuvirAmiodaroneChecker().check(_meds("sofosbuvir", "amiodarone"))
    assert findings
    ranks = {Severity.HIGH: 3, Severity.CRITICAL: 4}
    assert ranks[findings[0].severity] >= 3
