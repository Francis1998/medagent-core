"""Tests for the cumulative anticholinergic-burden safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety.anticholinergic_burden_checker import AnticholinergicBurdenChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names.

    Args:
        names: Medication display names.

    Returns:
        Medication objects for each name.
    """
    return [Medication(name=name) for name in names]


def test_flags_single_strong_anticholinergic() -> None:
    """A lone strong (score-3) anticholinergic is flagged at MODERATE baseline."""
    findings = AnticholinergicBurdenChecker().check(_meds("Diphenhydramine 25mg"))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "diphenhydramine"
    assert finding.anticholinergic_score == 3
    assert finding.total_burden == 3
    # A single score-3 agent already reaches the significance threshold.
    assert finding.severity is Severity.HIGH


def test_unrelated_medications_are_not_flagged() -> None:
    """Medications with no anticholinergic activity are ignored."""
    findings = AnticholinergicBurdenChecker().check(_meds("Metformin", "Lisinopril"))

    assert findings == []


def test_cumulative_burden_elevates_mild_agents() -> None:
    """Several mild agents summing to >=3 elevate every finding to HIGH."""
    findings = AnticholinergicBurdenChecker().check(_meds("Ranitidine", "Trazodone", "Loratadine"))

    assert len(findings) == 3
    for finding in findings:
        assert finding.anticholinergic_score == 1
        assert finding.total_burden == 3
        assert finding.severity is Severity.HIGH


def test_sub_threshold_burden_stays_low() -> None:
    """A single mild agent (total burden 1) stays below the significance threshold."""
    findings = AnticholinergicBurdenChecker().check(_meds("Ranitidine 150mg"))

    assert len(findings) == 1
    assert findings[0].total_burden == 1
    assert findings[0].severity is Severity.LOW


def test_duplicate_agent_entries_do_not_double_count_burden() -> None:
    """The same agent listed twice must not double-count its ACB burden.

    Cumulative burden is a sum over *distinct* anticholinergic agents. When the
    same agent appears in two medication entries (common after medication
    reconciliation or brand/generic double-listing), counting each entry
    previously inflated the total (2 -> 4 here), spuriously crossing the
    significance threshold (3) and over-escalating every finding to HIGH. The
    total must reflect the single distinct agent's score and stay LOW.
    """
    findings = AnticholinergicBurdenChecker().check(
        _meds("Cimetidine 400mg", "Cimetidine (Tagamet)")
    )

    assert len(findings) == 2
    for finding in findings:
        assert finding.agent == "cimetidine"
        assert finding.total_burden == 2
        assert finding.severity is Severity.LOW


def test_distinct_agents_still_sum_across_the_threshold() -> None:
    """Distinct agents continue to accumulate into the significant-burden band."""
    findings = AnticholinergicBurdenChecker().check(
        _meds("Diphenhydramine 25mg", "Cimetidine 400mg")
    )

    assert len(findings) == 2
    for finding in findings:
        assert finding.total_burden == 5
        assert finding.severity is Severity.HIGH


def test_whole_token_matching_avoids_false_substrings() -> None:
    """Matching is on whole tokens, so a substring does not trigger a finding."""
    findings = AnticholinergicBurdenChecker().check(_meds("Superatropineish tonic"))

    assert findings == []


def test_highest_scoring_agent_reported_for_multi_match() -> None:
    """A medication naming two agents reports the higher-scoring one."""
    findings = AnticholinergicBurdenChecker().check(_meds("atropine-ranitidine research blend"))

    assert len(findings) == 1
    assert findings[0].agent == "atropine"
    assert findings[0].anticholinergic_score == 3
