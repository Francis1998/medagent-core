"""Tests for the clozapine + CYP1A2 inhibitor exposure checker."""

from medagent.models import ClozapineCyp1a2Risk, Medication, Severity
from medagent.safety import ClozapineCyp1a2Checker as ExportedChecker
from medagent.safety.clozapine_cyp1a2_checker import ClozapineCyp1a2Checker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = ClozapineCyp1a2Checker()
    assert checker.check(_meds("Clozapine 100 mg")) == []
    assert checker.check(_meds("Fluvoxamine 100 mg")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = ClozapineCyp1a2Checker().check(_meds("Clozapine 100 mg", "Fluvoxamine 100 mg"))[0]

    assert isinstance(finding, ClozapineCyp1a2Risk)
    assert finding.agent == "clozapine"
    assert finding.partner_agent == "fluvoxamine"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "seizure" in finding.rationale.lower() or "myocarditis" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["clozapine", "clozaril", "fazaclo", "versacloz"]:
        finding = ClozapineCyp1a2Checker().check(
            _meds(f"{primary_agent} dose", "Fluvoxamine 100 mg")
        )[0]
        assert finding.agent == primary_agent

    for partner_agent, label, severity in [
        ("fluvoxamine", "Fluvoxamine 100 mg", Severity.CRITICAL),
        ("luvox", "Luvox 100 mg", Severity.CRITICAL),
        ("ciprofloxacin", "Ciprofloxacin 500 mg", Severity.HIGH),
        ("cipro", "Cipro 500 mg", Severity.HIGH),
    ]:
        finding = ClozapineCyp1a2Checker().check(_meds("Clozapine 100 mg", label))[0]
        assert finding.partner_agent == partner_agent
        assert finding.severity is severity


def test_related_but_out_of_scope_agents_do_not_flag() -> None:
    checker = ClozapineCyp1a2Checker()
    # Distinct from ANC monitoring and other CYP1A2 screens (e.g. theophylline)
    for agent in ["Olanzapine", "Theophylline", "Levofloxacin", "Sertraline"]:
        assert checker.check(_meds("Clozapine 100 mg", agent)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = ClozapineCyp1a2Checker()
    assert checker.check(_meds("Clozapinelike", "Fluvoxaminefree")) == []
    assert len(checker.check(_meds("Clozaril", "Fluvoxamine"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Ciprofloxacin 500 mg", "Clozapine 100 mg", "Fluvoxamine 100 mg"]
    forward = ClozapineCyp1a2Checker().check(_meds(*names))
    reverse = ClozapineCyp1a2Checker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert (
        len(
            ClozapineCyp1a2Checker().check(
                _meds(
                    "Clozapine 100 mg",
                    "Clozapine 50 mg",
                    "Fluvoxamine 100 mg",
                    "Fluvoxamine 50 mg",
                )
            )
        )
        == 1
    )


def test_findings_sorted_by_severity_first() -> None:
    findings = ClozapineCyp1a2Checker().check(
        _meds("Clozapine 100 mg", "Ciprofloxacin 500 mg", "Fluvoxamine 100 mg")
    )
    assert [finding.severity for finding in findings] == [Severity.CRITICAL, Severity.HIGH]
    assert findings[0].partner_agent == "fluvoxamine"
    assert findings[1].partner_agent == "ciprofloxacin"


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        ClozapineCyp1a2Checker().check(_meds("Clozapine and fluvoxamine interaction warning")) == []
    )
    finding = ExportedChecker().check(_meds("Versacloz", "Cipro"))[0]
    assert finding.severity is Severity.HIGH
