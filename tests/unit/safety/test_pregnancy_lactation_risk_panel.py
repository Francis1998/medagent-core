"""Tests for pregnancy/lactation risk panel (aggregate reproductive summary)."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import PregnancyLactationRiskPanel as ExportedPanel
from medagent.safety.pregnancy_lactation_risk_panel import PregnancyLactationRiskPanel


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_panel_summary_counts() -> None:
    findings = PregnancyLactationRiskPanel().check(
        medications=_meds("Warfarin", "Codeine"),
        pregnant=True,
        breastfeeding=True,
    )
    summary = next(f for f in findings if f.finding_kind == "panel_summary")
    assert summary.pregnancy_hit_count == 1
    assert summary.lactation_hit_count == 1
    assert summary.dual_hit_count == 0
    assert "RESEARCH USE ONLY" in summary.rationale


def test_pregnancy_aggregate() -> None:
    findings = PregnancyLactationRiskPanel().check(
        medications=_meds("Warfarin", "Valproate", "Metformin"),
        pregnant=True,
        breastfeeding=False,
    )
    kinds = {f.finding_kind for f in findings}
    assert "pregnancy_aggregate" in kinds
    aggregate = next(f for f in findings if f.finding_kind == "pregnancy_aggregate")
    assert aggregate.pregnancy_hit_count == 2
    assert set(aggregate.pregnancy_agents) == {"warfarin", "valproate"}


def test_lactation_aggregate() -> None:
    findings = PregnancyLactationRiskPanel().check(
        medications=_meds("Amiodarone", "Codeine"),
        pregnant=False,
        breastfeeding=True,
    )
    aggregate = next(f for f in findings if f.finding_kind == "lactation_aggregate")
    assert aggregate.lactation_hit_count == 2
    assert set(aggregate.lactation_agents) == {"amiodarone", "codeine"}


def test_dual_hit_methotrexate() -> None:
    findings = PregnancyLactationRiskPanel().check(
        medications=_meds("Methotrexate 10mg"),
        pregnant=True,
        breastfeeding=True,
    )
    dual = next(f for f in findings if f.finding_kind == "dual_hit_aggregate")
    assert dual.dual_hit_agents == ["methotrexate"]
    assert dual.dual_hit_count == 1
    assert dual.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in dual.rationale


def test_trimester_context_ace_inhibitor() -> None:
    findings = PregnancyLactationRiskPanel().check(
        medications=_meds("Lisinopril"),
        pregnant=True,
        breastfeeding=False,
        trimester="second",
    )
    context = next(f for f in findings if f.finding_kind == "trimester_context")
    assert context.trimester == "2"
    assert "lisinopril" in context.pregnancy_agents
    assert context.severity is Severity.HIGH


def test_no_findings_when_flags_false() -> None:
    findings = PregnancyLactationRiskPanel().check(
        medications=_meds("Warfarin", "Codeine"),
        pregnant=False,
        breastfeeding=False,
    )
    assert findings == []


def test_no_findings_for_benign_meds() -> None:
    findings = PregnancyLactationRiskPanel().check(
        medications=_meds("Metformin", "Acetaminophen"),
        pregnant=True,
        breastfeeding=True,
    )
    assert findings == []


def test_deduplicates_same_agent() -> None:
    findings = PregnancyLactationRiskPanel().check(
        medications=_meds("Lithium carbonate", "Lithium citrate"),
        pregnant=True,
        breastfeeding=True,
    )
    summary = next(f for f in findings if f.finding_kind == "panel_summary")
    assert summary.pregnancy_hit_count == 1
    assert summary.lactation_hit_count == 1
    assert summary.dual_hit_count == 1


def test_whole_token_matching() -> None:
    findings = PregnancyLactationRiskPanel().check(
        medications=_meds("Pseudowarfarin compound"),
        pregnant=True,
        breastfeeding=True,
    )
    assert findings == []


def test_findings_sorted_by_severity() -> None:
    findings = PregnancyLactationRiskPanel().check(
        medications=_meds("Methotrexate", "Warfarin"),
        pregnant=True,
        breastfeeding=True,
    )
    assert findings
    assert findings[0].severity is Severity.CRITICAL


def test_exported_from_safety_package() -> None:
    findings = ExportedPanel().check(
        medications=_meds("Isotretinoin", "Tramadol"),
        pregnant=True,
        breastfeeding=True,
    )
    assert any(f.finding_kind == "panel_summary" for f in findings)
    assert all("RESEARCH USE ONLY" in f.rationale for f in findings)
