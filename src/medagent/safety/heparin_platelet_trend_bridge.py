"""Heparin / LMWH exposure + falling platelet trend HIT-risk bridge.

The existing :class:`~medagent.safety.lab_trend_alert_bridge.LabTrendAlertBridge`
flags generic falling platelets without heparin context, and single-draw
critical-value checkers do not combine serial platelet trends with anticoagulant
exposure.

This bridge fills that gap: it combines heparin / UFH / LMWH agents with serial
platelet counts into advisory :class:`~medagent.models.HeparinPlateletTrendAlert`
findings (HIT-risk cues). RESEARCH USE ONLY; never modifies medications.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from medagent.logging_config import get_logger
from medagent.models import HeparinPlateletTrendAlert, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_AGENT_CLASS: Final[dict[str, str]] = {
    "heparin": "ufh",
    "ufh": "ufh",
    "unfractionated": "ufh",
    "enoxaparin": "lmwh",
    "dalteparin": "lmwh",
    "tinzaparin": "lmwh",
    "nadroparin": "lmwh",
    "fondaparinux": "other",
}

_PLATELET_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "platelets",
        "platelet",
        "plt",
        "platelet count",
        "plt count",
        "thrombocytes",
    }
)

# Relative decline thresholds used for HIT-risk cues (advisory only).
_HIT_PERCENT_DECLINE: Final[float] = -50.0
_MODERATE_PERCENT_DECLINE: Final[float] = -20.0
_LOW_PLATELET: Final[float] = 100.0
_CRITICAL_PLATELET: Final[float] = 50.0


class HeparinPlateletTrendBridge:
    """Map heparin/LMWH exposure + serial platelets to HIT-risk cues."""

    def check(
        self,
        medications: list[Medication],
        labs: Sequence[Mapping[str, Any]] | None = None,
    ) -> list[HeparinPlateletTrendAlert]:
        """Return heparin + platelet-trend HIT-risk alerts.

        Args:
            medications: Active medications.
            labs: Optional serial lab draws with ``name``, ``value``, optional
                ``unit`` / ``drawn_at``.

        Returns:
            Zero or more :class:`HeparinPlateletTrendAlert` findings. Distinct
            from generic :class:`LabTrendAlertBridge` platelet trends without
            heparin context. Never modifies medications.
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

        agents = [agent for _med, agent, _cls in matched]
        classes = sorted({cls for _med, _agent, cls in matched})
        med_names = sorted({med for med, _agent, _cls in matched}, key=str.casefold)

        series: list[tuple[str, float, str]] = []
        for entry in labs or []:
            name = str(entry.get("name", "")).strip().lower()
            if name not in _PLATELET_ALIASES and "platelet" not in name and name != "plt":
                continue
            try:
                value = float(entry.get("value"))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            unit = str(entry.get("unit") or "x10e9/L")
            drawn = str(entry.get("drawn_at") or "")
            series.append((drawn, value, unit))
        series.sort(key=lambda item: item[0])
        values = [value for _drawn, value, _unit in series]
        drawn_ats = [drawn for drawn, _value, _unit in series]
        unit = series[-1][2] if series else "x10e9/L"
        latest = values[-1] if values else None
        percent: float | None = None
        if len(values) >= 2 and values[0] != 0:
            percent = (values[-1] - values[0]) / values[0] * 100.0

        if not agents:
            logger.info("heparin_platelet_trend_bridge_checked", findings=0)
            return []

        findings: list[HeparinPlateletTrendAlert] = []

        def _add(kind: str, severity: Severity, rationale: str) -> None:
            findings.append(
                HeparinPlateletTrendAlert(
                    finding_kind=kind,
                    agents=agents,
                    agent_classes=classes,
                    medication_names=med_names,
                    platelet_values=values,
                    platelet_unit=unit,
                    drawn_ats=drawn_ats,
                    latest_platelet=latest,
                    percent_change=percent,
                    severity=severity,
                    rationale=rationale,
                )
            )

        falling = len(values) >= 2 and values[-1] < values[0]
        significant = percent is not None and percent <= _MODERATE_PERCENT_DECLINE
        hit_grade = percent is not None and percent <= _HIT_PERCENT_DECLINE
        low = latest is not None and latest < _LOW_PLATELET
        critical_low = latest is not None and latest < _CRITICAL_PLATELET

        if falling and "ufh" in classes:
            sev = Severity.CRITICAL if hit_grade or critical_low else Severity.HIGH
            _add(
                "falling_platelets_on_heparin",
                sev,
                (
                    "RESEARCH USE ONLY: Falling platelet trend on UFH/heparin "
                    f"therapy (values {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + f"). Agents: {', '.join(agents)}. HIT-risk bridge distinct "
                    "from generic LabTrendAlertBridge. Never modifies medications. "
                    "Confirm with a qualified clinician; prefer GPT-5.5 / Claude "
                    "Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if falling and "lmwh" in classes:
            sev = Severity.CRITICAL if hit_grade or critical_low else Severity.HIGH
            _add(
                "falling_platelets_on_lmwh",
                sev,
                (
                    "RESEARCH USE ONLY: Falling platelet trend on LMWH therapy "
                    f"(values {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + f"). Agents: {', '.join(agents)}. HIT-risk bridge distinct "
                    "from generic LabTrendAlertBridge. Never modifies medications. "
                    "Confirm with a qualified clinician; prefer GPT-5.5 / Claude "
                    "Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if (hit_grade or (falling and low)) and agents:
            _add(
                "hit_risk_platelet_decline",
                Severity.CRITICAL if hit_grade or critical_low else Severity.HIGH,
                (
                    "RESEARCH USE ONLY: HIT-risk platelet decline while on "
                    f"heparin-class agents {', '.join(agents)} (values {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + "). Advisory cue combining exposure + serial platelets; "
                    "distinct from drug-agnostic LabTrendAlertBridge. Never "
                    "modifies medications. Confirm with a qualified clinician; "
                    "prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if agents and len(values) >= 2 and (falling or significant):
            # Broad exposure+trend cue when any heparin-class agent + directional drop
            if not any(
                finding.finding_kind
                in {
                    "falling_platelets_on_heparin",
                    "falling_platelets_on_lmwh",
                    "hit_risk_platelet_decline",
                }
                for finding in findings
            ):
                _add(
                    "heparin_exposure_platelet_trend",
                    Severity.HIGH if falling else Severity.MODERATE,
                    (
                        "RESEARCH USE ONLY: Heparin-class exposure "
                        f"({', '.join(agents)}) with serial platelet trend "
                        f"{values}. Bridge advisory distinct from generic "
                        "LabTrendAlertBridge. Never modifies medications. "
                        "Confirm with a qualified clinician; prefer GPT-5.5 / "
                        "Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                    ),
                )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info("heparin_platelet_trend_bridge_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
