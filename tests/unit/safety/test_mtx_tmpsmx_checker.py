"""Tests for the methotrexate + TMP-SMX toxicity interaction safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import MtxTmpsmxChecker as ExportedChecker
from medagent.safety.mtx_tmpsmx_checker import MtxTmpsmxChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_without_methotrexate() -> None:
    """TMP-SMX alone yields no methotrexate × TMP-SMX findings."""
    findings = MtxTmpsmxChecker().check(
        _meds("Bactrim DS one tablet BID"),
    )

    assert findings == []


def test_no_findings_with_methotrexate_alone() -> None:
    """Methotrexate without TMP-SMX yields no findings."""
    findings = MtxTmpsmxChecker().check(
        _meds("Methotrexate 15 mg weekly"),
    )

    assert findings == []


def test_flags_methotrexate_plus_bactrim_critical() -> None:
    """Methotrexate + Bactrim yields a CRITICAL finding."""
    findings = MtxTmpsmxChecker().check(
        _meds("Methotrexate 15 mg weekly", "Bactrim DS one tablet BID"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "methotrexate"
    assert finding.partner_agent == "bactrim"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "myelosuppression" in finding.rationale.lower()


def test_flags_all_tmpsmx_panel_agents() -> None:
    """Each TMP-SMX panel agent can participate in a finding."""
    partners = [
        "trimethoprim",
        "sulfamethoxazole",
        "bactrim",
        "septra",
        "cotrimoxazole",
    ]

    for partner in partners:
        findings = MtxTmpsmxChecker().check(
            _meds("Methotrexate 10 mg weekly", f"{partner.title()} tablet"),
        )
        assert len(findings) == 1
        assert findings[0].partner_agent == partner
        assert findings[0].severity is Severity.CRITICAL


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match panel agents."""
    findings = MtxTmpsmxChecker().check(
        _meds("Pseudomethotrexate compound", "Bactrimoid supplement"),
    )

    assert findings == []
    real = MtxTmpsmxChecker().check(
        _meds("Methotrexate 15 mg weekly", "Trimethoprim 160 mg"),
    )
    assert len(real) == 1


def test_duplicate_medication_entries_do_not_duplicate_pairs() -> None:
    """Duplicate list entries for the same agents do not duplicate pair findings."""
    findings = MtxTmpsmxChecker().check(
        _meds(
            "Methotrexate 15 mg weekly",
            "Methotrexate 7.5 mg weekly",
            "Septra DS one tablet BID",
        ),
    )

    assert len(findings) == 1


def test_multiple_tmpsmx_partners_produce_multiple_findings() -> None:
    """One methotrexate with two TMP-SMX partners yields two findings."""
    findings = MtxTmpsmxChecker().check(
        _meds(
            "Methotrexate 15 mg weekly",
            "Trimethoprim 160 mg",
            "Cotrimoxazole 480 mg",
        ),
    )

    assert len(findings) == 2
    partner_agents = {finding.partner_agent for finding in findings}
    assert partner_agents == {"trimethoprim", "cotrimoxazole"}


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Methotrexate 15 mg weekly", "Bactrim DS one tablet BID"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "methotrexate"
    assert findings[0].partner_agent == "bactrim"
