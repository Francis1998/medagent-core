"""Tests for the clopidogrel + CYP2C19-inhibiting PPI safety checker."""

from __future__ import annotations

from medagent.models import ClopidogrelPpiRisk, Medication, Severity
from medagent.safety import ClopidogrelPpiChecker as ExportedChecker
from medagent.safety.clopidogrel_ppi_checker import ClopidogrelPpiChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    """Clopidogrel or a CYP2C19 PPI alone yields no finding."""
    checker = ClopidogrelPpiChecker()

    assert checker.check(_meds("Clopidogrel 75 mg daily")) == []
    assert checker.check(_meds("Omeprazole 20 mg daily")) == []
    assert checker.check([]) == []


def test_flags_clopidogrel_plus_omeprazole_high() -> None:
    """Clopidogrel + omeprazole yields a HIGH research-only finding."""
    findings = ClopidogrelPpiChecker().check(
        _meds("Clopidogrel 75 mg daily", "Omeprazole 20 mg daily")
    )

    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, ClopidogrelPpiRisk)
    assert finding.agent == "clopidogrel"
    assert finding.partner_agent == "omeprazole"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "CYP2C19" in finding.rationale


def test_plavix_plus_nexium_is_high() -> None:
    """Plavix + Nexium brand tokens yield HIGH severity."""
    finding = ClopidogrelPpiChecker().check(_meds("Plavix 75 mg daily", "Nexium 40 mg daily"))[0]

    assert finding.agent == "plavix"
    assert finding.partner_agent == "nexium"
    assert finding.severity is Severity.HIGH


def test_all_supported_agents_participate() -> None:
    """Every supported clopidogrel and PPI token can produce a finding."""
    for clopidogrel_agent in ["clopidogrel", "plavix"]:
        finding = ClopidogrelPpiChecker().check(
            _meds(f"{clopidogrel_agent.title()} 75 mg", "Omeprazole 20 mg")
        )[0]
        assert finding.agent == clopidogrel_agent

    for ppi_agent in ["omeprazole", "esomeprazole", "prilosec", "nexium"]:
        finding = ClopidogrelPpiChecker().check(
            _meds("Clopidogrel 75 mg", f"{ppi_agent.title()} 20 mg")
        )[0]
        assert finding.partner_agent == ppi_agent


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes do not match either medication panel."""
    checker = ClopidogrelPpiChecker()

    assert checker.check(_meds("Pseudoclopidogrel compound", "Omeprazoleish supplement")) == []
    assert len(checker.check(_meds("Clopidogrel 75 mg", "Omeprazole 20 mg"))) == 1


def test_duplicate_entries_do_not_duplicate_canonical_pairs() -> None:
    """Duplicate entries for the same agents yield one canonical pair."""
    findings = ClopidogrelPpiChecker().check(
        _meds(
            "Clopidogrel 75 mg",
            "Clopidogrel 75 mg daily",
            "Omeprazole 20 mg",
            "Omeprazole 20 mg daily",
        )
    )

    assert len(findings) == 1


def test_single_entry_is_not_treated_as_coprescription() -> None:
    """Two class names in one display string do not represent two prescriptions."""
    assert ClopidogrelPpiChecker().check(_meds("Clopidogrel and omeprazole interaction note")) == []


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    finding = ExportedChecker().check(_meds("Clopidogrel 75 mg", "Esomeprazole 40 mg"))[0]

    assert finding.agent == "clopidogrel"
    assert finding.partner_agent == "esomeprazole"
    assert finding.severity is Severity.HIGH
