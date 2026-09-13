"""Tests for SGLT2 inhibitor euglycemic DKA risk bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import Sglt2EuglycemicDkaBridge as ExportedBridge
from medagent.safety.hypoglycemia_risk_bridge import HypoglycemiaRiskBridge
from medagent.safety.metformin_contrast_checker import MetforminContrastChecker
from medagent.safety.sglt2_euglycemic_dka_bridge import Sglt2EuglycemicDkaBridge


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_perioperative_sglt2_dka_risk() -> None:
    findings = Sglt2EuglycemicDkaBridge().check(
        medications=_meds("Empagliflozin 10 mg"),
        surgery_flag=True,
    )
    hit = next(f for f in findings if f.finding_kind == "sglt2_perioperative_dka_risk")
    assert hit.severity in {Severity.HIGH, Severity.CRITICAL}
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale
    assert "empagliflozin" in hit.agents


def test_illness_sglt2_dka_risk() -> None:
    findings = Sglt2EuglycemicDkaBridge().check(
        medications=_meds("Dapagliflozin"),
        illness_flag=True,
    )
    assert any(f.finding_kind == "sglt2_illness_dka_risk" for f in findings)


def test_euglycemic_acidosis_cue() -> None:
    labs = [
        {"name": "glucose", "value": 110, "unit": "mg/dL", "drawn_at": "2026-01-01"},
        {"name": "bicarbonate", "value": 12, "unit": "mEq/L", "drawn_at": "2026-01-01"},
        {"name": "anion gap", "value": 22, "drawn_at": "2026-01-01"},
    ]
    findings = Sglt2EuglycemicDkaBridge().check(
        medications=_meds("Canagliflozin"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "sglt2_euglycemic_acidosis_cue")
    assert hit.severity is Severity.CRITICAL
    assert hit.latest_glucose == 110.0
    assert hit.acidosis_cues


def test_normal_glucose_with_ketones() -> None:
    labs = [
        {"name": "blood glucose", "value": 95, "drawn_at": "t1"},
        {"name": "serum ketones", "value": 3.5, "drawn_at": "t1"},
    ]
    findings = Sglt2EuglycemicDkaBridge().check(
        medications=_meds("Ertugliflozin"),
        labs=labs,
    )
    assert any(f.finding_kind == "sglt2_euglycemic_acidosis_cue" for f in findings)


def test_no_sglt2_no_findings() -> None:
    assert (
        Sglt2EuglycemicDkaBridge().check(
            medications=_meds("Metformin"),
            surgery_flag=True,
            illness_flag=True,
            labs=[{"name": "glucose", "value": 100}, {"name": "bicarbonate", "value": 10}],
        )
        == []
    )


def test_sglt2_without_risk_cues() -> None:
    findings = Sglt2EuglycemicDkaBridge().check(
        medications=_meds("Empagliflozin"),
        labs=[{"name": "glucose", "value": 180, "drawn_at": "a"}],
    )
    assert findings == []


def test_distinct_from_hypoglycemia_and_metformin_contrast() -> None:
    meds = _meds("Empagliflozin", "Metformin")
    labs = [
        {"name": "glucose", "value": 105, "drawn_at": "1"},
        {"name": "bicarbonate", "value": 11, "drawn_at": "1"},
    ]
    dka = Sglt2EuglycemicDkaBridge().check(medications=meds, labs=labs)
    assert dka
    # Hypoglycemia bridge requires insulin/SU — SGLT2 alone should not fire it
    assert HypoglycemiaRiskBridge().check(medications=_meds("Empagliflozin"), labs=labs) == []
    # Metformin contrast is a different control (contrast exposure), not euglycemic DKA
    assert MetforminContrastChecker is not Sglt2EuglycemicDkaBridge


def test_whole_token_matching() -> None:
    findings = Sglt2EuglycemicDkaBridge().check(
        medications=_meds("Pseudoempagliflozin"),
        surgery_flag=True,
    )
    assert findings == []


def test_never_modifies_medications() -> None:
    meds = _meds("Empagliflozin", "Dapagliflozin")
    snapshot = [(m.name, m.model_dump()) for m in meds]
    findings = Sglt2EuglycemicDkaBridge().check(
        medications=meds,
        surgery_flag=True,
        illness_flag=True,
    )
    assert findings
    assert [(m.name, m.model_dump()) for m in meds] == snapshot
    assert all("RESEARCH USE ONLY" in f.rationale for f in findings)


def test_exported() -> None:
    findings = ExportedBridge().check(
        medications=_meds("Canagliflozin"),
        illness_flag=True,
    )
    assert findings
    assert all("Never modifies medications" in f.rationale for f in findings)
