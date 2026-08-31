"""Tests for the sotalol QT safety checker."""

from medagent.models import Medication, Severity, SotalolQtRisk
from medagent.safety import SotalolQtChecker as ExportedChecker
from medagent.safety.sotalol_qt_checker import SotalolQtChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_without_sotalol() -> None:
    checker = SotalolQtChecker()
    assert checker.check(_meds("Ondansetron dose")) == []
    assert checker.check(_meds("Haloperidol dose", "Levofloxacin dose")) == []
    assert checker.check([]) == []


def test_sotalol_alone_is_high() -> None:
    finding = SotalolQtChecker().check(_meds("Sotalol dose"))[0]
    assert isinstance(finding, SotalolQtRisk)
    assert finding.agent == "sotalol"
    assert finding.partner_agent == ""
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "qt" in finding.rationale.lower()


def test_sotalol_with_ondansetron_escalates_to_critical() -> None:
    finding = SotalolQtChecker().check(_meds("Betapace dose", "Ondansetron dose"))[0]
    assert finding.agent == "betapace"
    assert finding.partner_agent == "ondansetron"
    assert finding.severity is Severity.CRITICAL
    assert "intensified" in finding.rationale.lower() or "escalat" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["sotalol", "betapace", "sorine", "sotylize"]:
        finding = SotalolQtChecker().check(_meds(f"{primary_agent} dose"))[0]
        assert finding.agent == primary_agent
        assert finding.severity is Severity.HIGH
    for partner_agent in [
        "ondansetron",
        "zofran",
        "levofloxacin",
        "levaquin",
        "haloperidol",
        "haldol",
        "amiodarone",
        "cordarone",
        "azithromycin",
        "zithromax",
    ]:
        finding = SotalolQtChecker().check(_meds("Sotalol dose", f"{partner_agent} dose"))[0]
        assert finding.partner_agent == partner_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = SotalolQtChecker()
    assert checker.check(_meds("sotalollike", "ondansetronlike")) == []
    assert len(checker.check(_meds("Sotalol", "Ondansetron"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Ondansetron dose", "Sotalol dose", "Haloperidol dose"]
    forward = SotalolQtChecker().check(_meds(*names))
    reverse = SotalolQtChecker().check(_meds(*reversed(names)))
    assert [(i.agent, i.partner_agent) for i in forward] == [
        (i.agent, i.partner_agent) for i in reverse
    ]
    assert (
        len(
            SotalolQtChecker().check(
                _meds("Sotalol a", "Sotalol b", "Ondansetron a", "Ondansetron b")
            )
        )
        == 1
    )


def test_findings_sorted_by_severity_first() -> None:
    findings = SotalolQtChecker().check(
        _meds("Sotalol dose", "Azithromycin dose", "Ondansetron dose")
    )
    assert [finding.severity for finding in findings] == [Severity.CRITICAL, Severity.HIGH]
    assert findings[0].partner_agent == "ondansetron"
    assert findings[1].partner_agent == "azithromycin"


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    alone = SotalolQtChecker().check(_meds("sotalol and ondansetron interaction warning"))
    assert len(alone) == 1
    assert alone[0].severity is Severity.HIGH
    assert alone[0].partner_agent == ""
    finding = ExportedChecker().check(_meds("Betapace AF dose", "Levaquin dose"))[0]
    assert finding.agent == "betapace af"
    assert finding.partner_agent == "levaquin"
    assert finding.severity is Severity.CRITICAL
