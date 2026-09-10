"""Hypoglycemia risk bridge - insulin/SU agents + serial glucose cues.

The existing :class:`~medagent.safety.lab_critical_value_checker.LabCriticalValueChecker`
flags single-draw panic glucose, and
:class:`~medagent.safety.lab_trend_alert_bridge.LabTrendAlertBridge`
covers creatinine/platelets/INR trends — not hypoglycemia-agent context.

This bridge fills that gap: it combines hypoglycemic agents with serial glucose
draws into advisory :class:`~medagent.models.HypoglycemiaRiskAlert` findings.
RESEARCH USE ONLY; never modifies medications.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from medagent.logging_config import get_logger
from medagent.models import HypoglycemiaRiskAlert, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_AGENT_CLASS: Final[dict[str, str]] = {
    "insulin": "insulin",
    "glargine": "insulin",
    "lispro": "insulin",
    "aspart": "insulin",
    "detemir": "insulin",
    "degludec": "insulin",
    "nph": "insulin",
    "humalog": "insulin",
    "novolog": "insulin",
    "lantus": "insulin",
    "glipizide": "sulfonylurea",
    "glyburide": "sulfonylurea",
    "glimepiride": "sulfonylurea",
    "gliclazide": "sulfonylurea",
    "repaglinide": "other",
    "nateglinide": "other",
}

_GLUCOSE_ALIASES: Final[frozenset[str]] = frozenset(
    {"glucose", "blood glucose", "bg", "fingerstick glucose", "serum glucose", "poc glucose"}
)

_LOW_GLUCOSE_MGDL: Final[float] = 70.0


class HypoglycemiaRiskBridge:
    """Map hypoglycemic agents + serial glucose to advisory risk cues."""

    def check(
        self,
        medications: list[Medication],
        labs: Sequence[Mapping[str, Any]] | None = None,
    ) -> list[HypoglycemiaRiskAlert]:
        """Return hypoglycemia risk alerts.

        Args:
            medications: Active medications.
            labs: Optional serial lab draws with ``name``, ``value``, optional
                ``unit`` / ``drawn_at``.

        Returns:
            Zero or more :class:`HypoglycemiaRiskAlert` findings.
        """
        matched: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & set(_AGENT_CLASS)):
                if agent in seen:
                    continue
                matched.append((medication.name, agent, _AGENT_CLASS[agent]))
                seen.add(agent)

        agents = [a for _m, a, _c in matched]
        classes = sorted({c for _m, _a, c in matched})
        med_names = sorted({m for m, _a, _c in matched}, key=str.casefold)

        glucose_series: list[tuple[str, float, str]] = []
        for entry in labs or []:
            name = str(entry.get("name", "")).strip().lower()
            if name not in _GLUCOSE_ALIASES and "glucose" not in name:
                continue
            try:
                value = float(entry.get("value"))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            unit = str(entry.get("unit") or "mg/dL")
            drawn = str(entry.get("drawn_at") or "")
            glucose_series.append((drawn, value, unit))
        glucose_series.sort(key=lambda item: item[0])
        values = [v for _d, v, _u in glucose_series]
        drawn_ats = [d for d, _v, _u in glucose_series]
        unit = glucose_series[-1][2] if glucose_series else "mg/dL"
        latest = values[-1] if values else None

        if not agents:
            logger.info("hypoglycemia_risk_bridge_checked", findings=0)
            return []

        findings: list[HypoglycemiaRiskAlert] = []

        def _add(kind: str, severity: Severity, rationale: str) -> None:
            findings.append(
                HypoglycemiaRiskAlert(
                    finding_kind=kind,
                    agents=agents,
                    agent_classes=classes,
                    medication_names=med_names,
                    glucose_values=values,
                    glucose_unit=unit,
                    drawn_ats=drawn_ats,
                    latest_glucose=latest,
                    severity=severity,
                    rationale=rationale,
                )
            )

        if len(classes) >= 2 or len(agents) >= 2:
            _add(
                "multi_hypoglycemic_agent_stack",
                Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Multi hypoglycemic-agent stack — "
                    f"{', '.join(agents)} (classes {', '.join(classes)}). "
                    "Never modifies medications. Confirm with a qualified "
                    "clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini "
                    "3.x / Kimi K2."
                ),
            )

        falling = len(values) >= 2 and values[-1] < values[0]
        low = latest is not None and latest < _LOW_GLUCOSE_MGDL

        if falling and "insulin" in classes:
            _add(
                "falling_glucose_on_insulin",
                Severity.CRITICAL if low else Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Falling glucose trend on insulin therapy "
                    f"(values {values}). Agents: {', '.join(agents)}. Distinct "
                    "from LabTrendAlertBridge non-glucose analytes. Never "
                    "modifies medications. Confirm with a qualified clinician; "
                    "prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )
        if falling and "sulfonylurea" in classes:
            _add(
                "falling_glucose_on_sulfonylurea",
                Severity.CRITICAL if low else Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Falling glucose trend on sulfonylurea "
                    f"(values {values}). Agents: {', '.join(agents)}. Never "
                    "modifies medications. Confirm with a qualified clinician; "
                    "prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )
        if low and agents:
            _add(
                "low_glucose_on_hypoglycemic_agent",
                Severity.CRITICAL,
                (
                    "RESEARCH USE ONLY: Latest glucose "
                    f"{latest} {unit} below {_LOW_GLUCOSE_MGDL} while on "
                    f"hypoglycemic agents {', '.join(agents)}. Distinct from "
                    "single-draw LabCriticalValueChecker. Never modifies "
                    "medications. Confirm with a qualified clinician; prefer "
                    "GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        findings.sort(key=lambda f: (-_SEVERITY_RANK[f.severity], f.finding_kind))
        logger.info("hypoglycemia_risk_bridge_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
