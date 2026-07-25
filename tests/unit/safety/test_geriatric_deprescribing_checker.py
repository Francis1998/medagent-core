"""Tests for the geriatric deprescribing-opportunity checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import GeriatricDeprescribingChecker as ExportedChecker
from medagent.safety.geriatric_deprescribing_checker import GeriatricDeprescribingChecker


def _med(name: str, *, frequency: str | None = None) -> Medication:
    """Build a medication with optional frequency metadata."""
    return Medication(name=name, frequency=frequency)


def test_no_findings_for_patient_under_65() -> None:
    """Deprescribing review is older-adult gated and does not apply under 65."""
    findings = GeriatricDeprescribingChecker().check([_med("Zolpidem 5mg")], age=50)

    assert findings == []


def test_no_findings_when_age_unknown() -> None:
    """Unknown age cannot establish geriatric deprescribing eligibility."""
    findings = GeriatricDeprescribingChecker().check([_med("Zolpidem 5mg")], age=None)

    assert findings == []


def test_flags_long_term_ppi_without_indication() -> None:
    """A scheduled PPI without a protective indication is a step-down candidate."""
    findings = GeriatricDeprescribingChecker().check(
        [_med("Omeprazole 20mg", frequency="daily")],
        age=75,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "omeprazole"
    assert finding.deprescribing_category == "long-term PPI without clear ongoing indication"
    assert finding.taper_candidate is True
    assert finding.severity is Severity.LOW
    assert "75" in finding.rationale
    assert "RESEARCH USE ONLY" in finding.rationale


def test_ppi_with_documented_indication_is_not_flagged() -> None:
    """Documented high-risk GI indications suppress the PPI deprescribing flag."""
    findings = GeriatricDeprescribingChecker().check(
        [_med("Pantoprazole 40mg", frequency="daily")],
        age=80,
        indications=["Barrett esophagus surveillance"],
    )

    assert findings == []


def test_ppi_without_long_term_signal_is_not_flagged() -> None:
    """A PPI without scheduled/chronic-use text is not treated as long-term."""
    findings = GeriatricDeprescribingChecker().check([_med("Pantoprazole 40mg")], age=80)

    assert findings == []


def test_flags_sedative_hypnotic_as_taper_candidate() -> None:
    """Z-drug hypnotics are flagged as deprescribing/taper opportunities."""
    findings = GeriatricDeprescribingChecker().check([_med("Zolpidem 5mg")], age=70)

    assert len(findings) == 1
    assert findings[0].agent == "zolpidem"
    assert findings[0].taper_candidate is True
    assert findings[0].severity is Severity.MODERATE
    assert "non-drug sleep strategies" in findings[0].suggested_action


def test_flags_first_generation_antihistamine() -> None:
    """First-generation antihistamines are deprescribing switch candidates."""
    findings = GeriatricDeprescribingChecker().check([_med("Diphenhydramine 25mg")], age=78)

    assert len(findings) == 1
    assert findings[0].agent == "diphenhydramine"
    assert findings[0].taper_candidate is False
    assert "anticholinergic" in findings[0].rationale


def test_chronic_nsaid_requires_long_term_signal() -> None:
    """NSAIDs are flagged only when medication text suggests scheduled use."""
    prn = GeriatricDeprescribingChecker().check([_med("Ibuprofen 400mg")], age=76)
    scheduled = GeriatricDeprescribingChecker().check(
        [_med("Ibuprofen 400mg", frequency="scheduled daily")],
        age=76,
    )

    assert prn == []
    assert len(scheduled) == 1
    assert scheduled[0].agent == "ibuprofen"
    assert scheduled[0].deprescribing_category == "chronic NSAID deprescribing candidate"


def test_multiple_findings_sorted_by_descending_severity_then_name() -> None:
    """Moderate findings sort ahead of low-severity PPI opportunities."""
    findings = GeriatricDeprescribingChecker().check(
        [
            _med("Omeprazole 20mg", frequency="daily"),
            _med("Zolpidem 5mg"),
        ],
        age=68,
    )

    assert [finding.agent for finding in findings] == ["zolpidem", "omeprazole"]
    assert findings[0].severity is Severity.MODERATE
    assert findings[1].severity is Severity.LOW


def test_whole_token_matching_avoids_false_positives() -> None:
    """Matching is whole-token, so substring look-alikes are ignored."""
    findings = GeriatricDeprescribingChecker().check([_med("Zolpidemesque compound")], age=75)

    assert findings == []
    real = GeriatricDeprescribingChecker().check([_med("Zolpidem 5mg")], age=75)
    assert len(real) == 1
    assert real[0].agent == "zolpidem"


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check([_med("Doxylamine 25mg")], age=72)

    assert len(findings) == 1
    assert findings[0].agent == "doxylamine"
