"""Tests for the serotonin-syndrome safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety.serotonin_syndrome_checker import SerotoninSyndromeChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names.

    Args:
        names: Medication display names.

    Returns:
        Medication objects for each name.
    """
    return [Medication(name=name) for name in names]


def test_single_serotonergic_agent_is_not_flagged() -> None:
    """A lone serotonergic drug is not serotonin syndrome and yields no finding."""
    findings = SerotoninSyndromeChecker().check(_meds("Sertraline 50mg"))

    assert findings == []


def test_unrelated_medications_are_not_flagged() -> None:
    """Medications outside the serotonergic list are ignored."""
    findings = SerotoninSyndromeChecker().check(_meds("Metformin", "Lisinopril"))

    assert findings == []


def test_same_agent_listed_twice_is_not_a_combination() -> None:
    """Duplicate entries of one serotonergic agent are not a combination.

    Serotonin syndrome requires two or more *distinct* serotonergic agents. The
    same drug listed twice (common after medication reconciliation or
    brand/generic double-listing) is a single agent, so counting raw entries
    previously produced a false serotonin-syndrome finding. No finding must be
    raised when only one distinct agent is present.
    """
    findings = SerotoninSyndromeChecker().check(_meds("Fluoxetine 20mg", "Fluoxetine 10mg"))

    assert findings == []


def test_concurrent_count_reflects_distinct_agents() -> None:
    """The concurrency count is over distinct agents, not raw list entries."""
    findings = SerotoninSyndromeChecker().check(
        _meds("Fluoxetine 20mg", "Fluoxetine 10mg", "Tramadol 50mg")
    )

    assert len(findings) == 3
    assert {finding.concurrent_serotonergic_medications for finding in findings} == {1}


def test_two_serotonergic_agents_are_flagged_high() -> None:
    """Two co-prescribed serotonergic agents raise a HIGH combination finding."""
    findings = SerotoninSyndromeChecker().check(_meds("Sertraline 50mg", "Tramadol 50mg"))

    assert len(findings) == 2
    for finding in findings:
        assert finding.severity is Severity.HIGH
        assert finding.concurrent_serotonergic_medications == 1
        assert "serotonin syndrome" in finding.rationale


def test_maoi_combination_is_critical() -> None:
    """Any MAOI combined with another serotonergic agent is CRITICAL."""
    findings = SerotoninSyndromeChecker().check(_meds("Phenelzine 15mg", "Fluoxetine 20mg"))

    assert len(findings) == 2
    for finding in findings:
        assert finding.severity is Severity.CRITICAL
        assert "contraindicated" in finding.rationale
    agents = {finding.agent for finding in findings}
    assert agents == {"phenelzine", "fluoxetine"}


def test_linezolid_counts_as_an_maoi() -> None:
    """Linezolid (a reversible MAOI antibiotic) triggers the CRITICAL escalation."""
    findings = SerotoninSyndromeChecker().check(_meds("Linezolid 600mg", "Citalopram 20mg"))

    assert len(findings) == 2
    assert all(finding.severity is Severity.CRITICAL for finding in findings)
    by_med = {finding.agent: finding.drug_class for finding in findings}
    assert by_med["linezolid"] == "MAOI"
    assert by_med["citalopram"] == "SSRI"


def test_findings_ordered_by_severity_then_name() -> None:
    """Findings are ordered worst-severity first, then by medication name."""
    findings = SerotoninSyndromeChecker().check(_meds("Venlafaxine", "Sumatriptan", "Duloxetine"))

    # All HIGH (no MAOI), so ordering falls back to medication name.
    assert [finding.medication for finding in findings] == [
        "Duloxetine",
        "Sumatriptan",
        "Venlafaxine",
    ]


def test_whole_token_matching_avoids_false_substrings() -> None:
    """Matching is on whole tokens, so a substring does not trigger a finding."""
    findings = SerotoninSyndromeChecker().check(
        _meds("Sertralinelike compound", "Tramadolish tonic")
    )

    assert findings == []


def test_maoi_preferred_when_medication_names_two_agents() -> None:
    """A medication naming two serotonergic agents reports the MAOI one."""
    findings = SerotoninSyndromeChecker().check(
        _meds("selegiline-fluoxetine research blend", "Tramadol")
    )

    assert len(findings) == 2
    blend = next(finding for finding in findings if "blend" in finding.medication)
    assert blend.agent == "selegiline"
    assert blend.drug_class == "MAOI"
    assert blend.severity is Severity.CRITICAL
