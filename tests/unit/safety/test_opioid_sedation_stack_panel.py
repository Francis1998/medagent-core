"""Tests for opioid sedation stack panel."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import OpioidSedationStackPanel as ExportedPanel
from medagent.safety.opioid_sedation_stack_panel import OpioidSedationStackPanel


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_triple_sedation_stack() -> None:
    findings = OpioidSedationStackPanel().check(
        medications=_meds("Oxycodone", "Lorazepam", "Gabapentin"),
    )
    triple = next(f for f in findings if f.finding_kind == "triple_sedation_stack")
    assert triple.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in triple.rationale


def test_opioid_benzo_stack() -> None:
    findings = OpioidSedationStackPanel().check(
        medications=_meds("Morphine", "Alprazolam"),
    )
    stack = next(f for f in findings if f.finding_kind == "opioid_benzo_stack")
    assert stack.severity is Severity.HIGH


def test_opioid_gabapentinoid_stack() -> None:
    findings = OpioidSedationStackPanel().check(
        medications=_meds("Hydrocodone", "Pregabalin"),
    )
    stack = next(f for f in findings if f.finding_kind == "opioid_gabapentinoid_stack")
    assert stack.gabapentinoids == ["pregabalin"]


def test_multi_opioid_stack() -> None:
    findings = OpioidSedationStackPanel().check(
        medications=_meds("Oxycodone", "Morphine"),
    )
    stack = next(f for f in findings if f.finding_kind == "multi_opioid_stack")
    assert len(stack.opioids) == 2


def test_no_findings_for_single_opioid() -> None:
    assert OpioidSedationStackPanel().check(medications=_meds("Oxycodone")) == []


def test_no_findings_for_benign() -> None:
    assert OpioidSedationStackPanel().check(medications=_meds("Metformin")) == []


def test_exported_from_safety_package() -> None:
    assert ExportedPanel is OpioidSedationStackPanel
