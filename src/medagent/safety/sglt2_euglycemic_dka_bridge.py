"""SGLT2 inhibitor euglycemic DKA risk bridge.

The existing :class:`~medagent.safety.hypoglycemia_risk_bridge.HypoglycemiaRiskBridge`
covers insulin/SU + falling glucose, and
:class:`~medagent.safety.metformin_contrast_checker.MetforminContrastChecker`
covers metformin + iodinated contrast — neither combines SGLT2 inhibitors with
perioperative/illness or euglycemic acidosis cues.

This bridge fills that gap: it maps SGLT2i exposure plus surgery/illness flags
or low/normal glucose with acidosis cues into advisory
:class:`~medagent.models.Sglt2EuglycemicDkaAlert` findings.
RESEARCH USE ONLY; never modifies medications.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, Sglt2EuglycemicDkaAlert

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_SGLT2_AGENTS: Final[frozenset[str]] = frozenset(
    {
        "empagliflozin",
        "dapagliflozin",
        "canagliflozin",
        "ertugliflozin",
    }
)

_GLUCOSE_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "glucose",
        "blood glucose",
        "bg",
        "fingerstick glucose",
        "serum glucose",
        "poc glucose",
    }
)

_ACIDOSIS_ALIASES: Final[dict[str, str]] = {
    "bicarbonate": "low_bicarbonate",
    "hco3": "low_bicarbonate",
    "serum bicarbonate": "low_bicarbonate",
    "anion gap": "elevated_anion_gap",
    "ag": "elevated_anion_gap",
    "ketones": "ketones",
    "serum ketones": "ketones",
    "beta hydroxybutyrate": "ketones",
    "betahydroxybutyrate": "ketones",
    "bhb": "ketones",
    "ph": "low_ph",
    "blood ph": "low_ph",
    "arterial ph": "low_ph",
}

# Euglycemic / near-euglycemic glucose ceiling (mg/dL) for DKA cue pairing.
_EUGLYCEMIC_GLUCOSE_MGDL: Final[float] = 250.0
_LOW_BICARB: Final[float] = 18.0
_HIGH_ANION_GAP: Final[float] = 12.0
_KETONE_POSITIVE: Final[float] = 0.6
_LOW_PH: Final[float] = 7.3


class Sglt2EuglycemicDkaBridge:
    """Map SGLT2i + surgery/illness or euglycemic acidosis cues to DKA advisories."""

    def check(
        self,
        medications: list[Medication],
        labs: Sequence[Mapping[str, Any]] | None = None,
        *,
        surgery_flag: bool = False,
        illness_flag: bool = False,
    ) -> list[Sglt2EuglycemicDkaAlert]:
        """Return SGLT2 euglycemic DKA advisory findings.

        Args:
            medications: Active medications.
            labs: Optional draws with ``name``, ``value``, optional ``unit`` /
                ``drawn_at`` (glucose and acidosis markers).
            surgery_flag: True when perioperative / surgery context is documented.
            illness_flag: True when acute illness context is documented.

        Returns:
            Zero or more :class:`Sglt2EuglycemicDkaAlert` findings. Distinct from
            :class:`HypoglycemiaRiskBridge` and :class:`MetforminContrastChecker`.
            Never modifies medications.
        """
        matched: list[tuple[str, str]] = []
        seen: set[str] = set()
        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & _SGLT2_AGENTS):
                if agent in seen:
                    continue
                matched.append((medication.name, agent))
                seen.add(agent)

        agents = [agent for _med, agent in matched]
        med_names = sorted({med for med, _agent in matched}, key=str.casefold)

        glucose_series: list[tuple[str, float, str]] = []
        acidosis_cues: list[str] = []
        for entry in labs or []:
            name = str(entry.get("name", "")).strip().lower()
            try:
                value = float(entry.get("value"))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            if name in _GLUCOSE_ALIASES or "glucose" in name:
                unit = str(entry.get("unit") or "mg/dL")
                drawn = str(entry.get("drawn_at") or "")
                glucose_series.append((drawn, value, unit))
                continue
            cue_kind = _ACIDOSIS_ALIASES.get(name)
            if cue_kind is None:
                for alias, kind in _ACIDOSIS_ALIASES.items():
                    if alias in name:
                        cue_kind = kind
                        break
            if cue_kind is None:
                continue
            if cue_kind == "low_bicarbonate" and value < _LOW_BICARB:
                acidosis_cues.append(f"{cue_kind}:{value}")
            elif cue_kind == "elevated_anion_gap" and value > _HIGH_ANION_GAP:
                acidosis_cues.append(f"{cue_kind}:{value}")
            elif cue_kind == "ketones" and value >= _KETONE_POSITIVE:
                acidosis_cues.append(f"{cue_kind}:{value}")
            elif cue_kind == "low_ph" and value < _LOW_PH:
                acidosis_cues.append(f"{cue_kind}:{value}")

        glucose_series.sort(key=lambda item: item[0])
        glucose_values = [value for _drawn, value, _unit in glucose_series]
        drawn_ats = [drawn for drawn, _value, _unit in glucose_series]
        glucose_unit = glucose_series[-1][2] if glucose_series else "mg/dL"
        latest_glucose = glucose_values[-1] if glucose_values else None
        euglycemic = latest_glucose is not None and latest_glucose <= _EUGLYCEMIC_GLUCOSE_MGDL

        if not agents:
            logger.info("sglt2_euglycemic_dka_bridge_checked", findings=0)
            return []

        findings: list[Sglt2EuglycemicDkaAlert] = []

        def _add(kind: str, severity: Severity, rationale: str) -> None:
            findings.append(
                Sglt2EuglycemicDkaAlert(
                    finding_kind=kind,
                    agents=agents,
                    medication_names=med_names,
                    glucose_values=glucose_values,
                    glucose_unit=glucose_unit,
                    drawn_ats=drawn_ats,
                    latest_glucose=latest_glucose,
                    acidosis_cues=sorted(set(acidosis_cues)),
                    surgery_flag=surgery_flag,
                    illness_flag=illness_flag,
                    severity=severity,
                    rationale=rationale,
                )
            )

        if surgery_flag:
            _add(
                "sglt2_perioperative_dka_risk",
                Severity.CRITICAL if acidosis_cues else Severity.HIGH,
                (
                    "RESEARCH USE ONLY: SGLT2 inhibitor "
                    f"({', '.join(agents)}) with perioperative/surgery context. "
                    "Euglycemic DKA advisory distinct from HypoglycemiaRiskBridge "
                    "and MetforminContrastChecker. Never modifies medications. "
                    "Confirm with a qualified clinician; prefer GPT-5.5 / Claude "
                    "Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if illness_flag:
            _add(
                "sglt2_illness_dka_risk",
                Severity.CRITICAL if acidosis_cues else Severity.HIGH,
                (
                    "RESEARCH USE ONLY: SGLT2 inhibitor "
                    f"({', '.join(agents)}) with acute illness context. "
                    "Euglycemic DKA advisory distinct from HypoglycemiaRiskBridge "
                    "and MetforminContrastChecker. Never modifies medications. "
                    "Confirm with a qualified clinician; prefer GPT-5.5 / Claude "
                    "Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if euglycemic and acidosis_cues:
            _add(
                "sglt2_euglycemic_acidosis_cue",
                Severity.CRITICAL,
                (
                    "RESEARCH USE ONLY: SGLT2 inhibitor "
                    f"({', '.join(agents)}) with low/normal glucose "
                    f"({latest_glucose} {glucose_unit}) and acidosis cues "
                    f"{sorted(set(acidosis_cues))}. Euglycemic DKA bridge "
                    "distinct from HypoglycemiaRiskBridge and "
                    "MetforminContrastChecker. Never modifies medications. "
                    "Confirm with a qualified clinician; prefer GPT-5.5 / Claude "
                    "Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info("sglt2_euglycemic_dka_bridge_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
