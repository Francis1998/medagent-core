"""Tests for the escitalopram / citalopram QT safety checker."""

from medagent.models import EscitalopramQtRisk, Medication, Severity
from medagent.safety import EscitalopramQtChecker as ExportedChecker
from medagent.safety.escitalopram_qt_checker import EscitalopramQtChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_without_primary() -> None:
    checker = EscitalopramQtChecker()
    assert checker.check(_meds("Ondansetron dose")) == []
    assert checker.check(_meds("Haloperidol dose", "Levofloxacin dose")) == []
    assert checker.check([]) == []


def test_escitalopram_alone_is_high() -> None:
    finding = EscitalopramQtChecker().check(_meds("Escitalopram dose"))[0]
    assert isinstance(finding, EscitalopramQtRisk)
    assert finding.agent == "escitalopram"
    assert finding.partner_agent == ""
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "qt" in finding.rationale.lower()


def test_citalopram_with_haloperidol_escalates_to_critical() -> None:
    finding = EscitalopramQtChecker().check(_meds("Celexa dose", "Haloperidol dose"))[0]
    assert finding.agent == "celexa"
    assert finding.partner_agent == "haloperidol"
    assert finding.severity is Severity.CRITICAL


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["escitalopram", "lexapro", "citalopram", "celexa"]:
        finding = EscitalopramQtChecker().check(_meds(f"{primary_agent} dose"))[0]
        assert finding.agent == primary_agent
        assert finding.severity is Severity.HIGH
    for partner_agent in [
        "ondansetron",
        "zofran",
        "haloperidol",
        "haldol",
        "amiodarone",
        "cordarone",
        "levofloxacin",
        "levaquin",
        "azithromycin",
        "zithromax",
    ]:
        finding = EscitalopramQtChecker().check(
            _meds("Escitalopram dose", f"{partner_agent} dose")
        )[0]
        assert finding.partner_agent == partner_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = EscitalopramQtChecker()
    assert checker.check(_meds("escitalopramlike", "ondansetronlike")) == []
    assert len(checker.check(_meds("Escitalopram", "Ondansetron"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Ondansetron dose", "Escitalopram dose", "Haloperidol dose"]
    forward = EscitalopramQtChecker().check(_meds(*names))
    reverse = EscitalopramQtChecker().check(_meds(*reversed(names)))
    assert [(i.agent, i.partner_agent) for i in forward] == [
        (i.agent, i.partner_agent) for i in reverse
    ]
    assert (
        len(
            EscitalopramQtChecker().check(
                _meds("Escitalopram a", "Escitalopram b", "Ondansetron a", "Ondansetron b")
            )
        )
        == 1
    )


def test_findings_sorted_by_severity_first() -> None:
    findings = EscitalopramQtChecker().check(
        _meds("Lexapro dose", "Azithromycin dose", "Ondansetron dose")
    )
    assert [finding.severity for finding in findings] == [Severity.CRITICAL, Severity.HIGH]
    assert findings[0].partner_agent == "ondansetron"
    assert findings[1].partner_agent == "azithromycin"


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    alone = EscitalopramQtChecker().check(_meds("escitalopram and ondansetron interaction warning"))
    assert len(alone) == 1
    assert alone[0].severity is Severity.HIGH
    assert alone[0].partner_agent == ""
    finding = ExportedChecker().check(_meds("Citalopram dose", "Zofran dose"))[0]
    assert finding.agent == "citalopram"
    assert finding.partner_agent == "zofran"
    assert finding.severity is Severity.CRITICAL
