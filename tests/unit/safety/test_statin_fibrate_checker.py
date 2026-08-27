"""Tests for the statin + fibrate myopathy / rhabdomyolysis checker."""

from medagent.models import Medication, Severity, StatinFibrateRisk
from medagent.safety import StatinFibrateChecker as ExportedChecker
from medagent.safety.statin_fibrate_checker import StatinFibrateChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = StatinFibrateChecker()
    assert checker.check(_meds("Simvastatin 40 mg nightly")) == []
    assert checker.check(_meds("Gemfibrozil 600 mg BID")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = StatinFibrateChecker().check(
        _meds("Simvastatin 40 mg nightly", "Gemfibrozil 600 mg BID")
    )[0]

    assert isinstance(finding, StatinFibrateRisk)
    assert finding.agent == "simvastatin"
    assert finding.partner_agent == "gemfibrozil"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "myopathy" in finding.rationale.lower() or "rhabdomyolysis" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in [
        "simvastatin",
        "zocor",
        "lovastatin",
        "mevacor",
        "altoprev",
        "atorvastatin",
        "lipitor",
        "rosuvastatin",
        "crestor",
        "pravastatin",
        "pravachol",
        "fluvastatin",
        "lescol",
        "pitavastatin",
        "livalo",
    ]:
        finding = StatinFibrateChecker().check(
            _meds(f"{primary_agent} dose", "Gemfibrozil 600 mg")
        )[0]
        assert finding.agent == primary_agent

    for partner_agent, label, severity in [
        ("gemfibrozil", "Gemfibrozil 600 mg", Severity.CRITICAL),
        ("lopid", "Lopid 600 mg", Severity.CRITICAL),
        ("fenofibrate", "Fenofibrate 145 mg", Severity.HIGH),
        ("tricor", "Tricor 145 mg", Severity.HIGH),
        ("lofibra", "Lofibra 160 mg", Severity.HIGH),
        ("fenofibric", "Fenofibric acid 135 mg", Severity.HIGH),
        ("trilipix", "Trilipix 135 mg", Severity.HIGH),
    ]:
        finding = StatinFibrateChecker().check(_meds("Simvastatin 40 mg", label))[0]
        assert finding.partner_agent == partner_agent
        assert finding.severity is severity


def test_related_but_out_of_scope_agents_do_not_flag() -> None:
    checker = StatinFibrateChecker()
    # Distinct from statin CYP3A4 and statin macrolide
    for agent in ["Clarithromycin", "Ketoconazole", "Erythromycin", "Niacin"]:
        assert checker.check(_meds("Simvastatin 40 mg", agent)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = StatinFibrateChecker()
    assert checker.check(_meds("Simvastatinlike", "Gemfibrozilfree")) == []
    assert len(checker.check(_meds("Simvastatin", "Gemfibrozil"))) == 1
    assert len(checker.check(_meds("Lipitor", "Tricor"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Gemfibrozil 600 mg", "Simvastatin 40 mg", "Fenofibrate 145 mg"]
    forward = StatinFibrateChecker().check(_meds(*names))
    reverse = StatinFibrateChecker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert (
        len(
            StatinFibrateChecker().check(
                _meds(
                    "Simvastatin 40 mg",
                    "Simvastatin 20 mg",
                    "Gemfibrozil 600 mg",
                    "Gemfibrozil 300 mg",
                )
            )
        )
        == 1
    )


def test_findings_sorted_by_severity_first() -> None:
    findings = StatinFibrateChecker().check(
        _meds("Simvastatin 40 mg", "Fenofibrate 145 mg", "Gemfibrozil 600 mg")
    )
    assert [finding.severity for finding in findings] == [Severity.CRITICAL, Severity.HIGH]
    assert findings[0].partner_agent == "gemfibrozil"
    assert findings[1].partner_agent == "fenofibrate"


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        StatinFibrateChecker().check(_meds("Simvastatin and gemfibrozil interaction warning")) == []
    )
    finding = ExportedChecker().check(_meds("Crestor 20 mg", "Lopid 600 mg"))[0]
    assert finding.agent == "crestor"
    assert finding.partner_agent == "lopid"
    assert finding.severity is Severity.CRITICAL
