"""Tests for the cyclosporine + statin safety checker."""

from medagent.models import CyclosporineStatinRisk, Medication, Severity
from medagent.safety import CyclosporineStatinChecker as ExportedChecker
from medagent.safety.cyclosporine_statin_checker import CyclosporineStatinChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = CyclosporineStatinChecker()
    assert checker.check(_meds("Cyclosporine dose")) == []
    assert checker.check(_meds("Simvastatin dose")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = CyclosporineStatinChecker().check(_meds("Cyclosporine dose", "Simvastatin dose"))[0]
    assert isinstance(finding, CyclosporineStatinRisk)
    assert finding.agent == "cyclosporine"
    assert finding.partner_agent == "simvastatin"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "rhabdomyolysis" in finding.rationale.lower()


def test_atorvastatin_pair_is_high_not_critical() -> None:
    finding = CyclosporineStatinChecker().check(_meds("Neoral dose", "Atorvastatin dose"))[0]
    assert finding.agent == "neoral"
    assert finding.partner_agent == "atorvastatin"
    assert finding.severity is Severity.HIGH


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["cyclosporine", "ciclosporin", "neoral", "sandimmune", "gengraf"]:
        finding = CyclosporineStatinChecker().check(
            _meds(f"{primary_agent} dose", "Simvastatin dose")
        )[0]
        assert finding.agent == primary_agent
    for partner_agent in [
        "simvastatin",
        "zocor",
        "lovastatin",
        "mevacor",
        "atorvastatin",
        "lipitor",
    ]:
        finding = CyclosporineStatinChecker().check(
            _meds("Cyclosporine dose", f"{partner_agent} dose")
        )[0]
        assert finding.partner_agent == partner_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = CyclosporineStatinChecker()
    assert checker.check(_meds("cyclosporinelike", "simvastatinlike")) == []
    assert len(checker.check(_meds("Cyclosporine", "Simvastatin"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Simvastatin dose", "Cyclosporine dose", "Lovastatin dose"]
    forward = CyclosporineStatinChecker().check(_meds(*names))
    reverse = CyclosporineStatinChecker().check(_meds(*reversed(names)))
    assert [(i.agent, i.partner_agent) for i in forward] == [
        (i.agent, i.partner_agent) for i in reverse
    ]
    assert (
        len(
            CyclosporineStatinChecker().check(
                _meds("Cyclosporine a", "Cyclosporine b", "Simvastatin a", "Simvastatin b")
            )
        )
        == 1
    )


def test_findings_sorted_by_severity_first() -> None:
    findings = CyclosporineStatinChecker().check(
        _meds("Cyclosporine dose", "Atorvastatin dose", "Simvastatin dose")
    )
    assert [finding.severity for finding in findings] == [Severity.CRITICAL, Severity.HIGH]
    assert findings[0].partner_agent == "simvastatin"
    assert findings[1].partner_agent == "atorvastatin"


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        CyclosporineStatinChecker().check(_meds("cyclosporine and simvastatin interaction warning"))
        == []
    )
    finding = ExportedChecker().check(_meds("Sandimmune dose", "Zocor dose"))[0]
    assert finding.agent == "sandimmune"
    assert finding.partner_agent == "zocor"
