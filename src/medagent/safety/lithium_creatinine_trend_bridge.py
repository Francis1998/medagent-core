"""Lithium + rising/elevated creatinine renal-risk bridge.

The existing :class:`~medagent.safety.lithium_acei_checker.LithiumAceiChecker`,
:class:`~medagent.safety.lithium_nsaid_checker.LithiumNsaidChecker`, and
:class:`~medagent.safety.lithium_thiazide_checker.LithiumThiazideChecker` cover
pairwise lithium DDIs that impair clearance.
:class:`~medagent.safety.lab_trend_alert_bridge.LabTrendAlertBridge` flags
drug-agnostic rising creatinine — none require lithium context for creatinine
trends.

This bridge fills that gap: it combines lithium exposure with rising or
elevated serial creatinine into advisory
:class:`~medagent.models.LithiumCreatinineTrendAlert` findings.
RESEARCH USE ONLY; never modifies medications.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from medagent.logging_config import get_logger
from medagent.models import LithiumCreatinineTrendAlert, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_LITHIUM_AGENTS: Final[frozenset[str]] = frozenset({"lithium", "lithobid", "eskalith"})

_CREATININE_ALIASES: Final[frozenset[str]] = frozenset(
    {"creatinine", "creat", "serum creatinine", "scr"}
)

# Advisory thresholds (mg/dL) — RESEARCH USE ONLY, not dosing guidance.
_ELEVATED_CREATININE: Final[float] = 1.3
_CRITICAL_CREATININE: Final[float] = 2.0
_MIN_RELATIVE_RISE: Final[float] = 0.2


class LithiumCreatinineTrendBridge:
    """Map lithium exposure + serial creatinine trends to renal-risk advisories."""

    def check(
        self,
        medications: list[Medication],
        labs: Sequence[Mapping[str, Any]] | None = None,
    ) -> list[LithiumCreatinineTrendAlert]:
        """Return lithium + creatinine-trend renal-risk alerts.

        Args:
            medications: Active medications.
            labs: Optional serial lab draws with ``name``, ``value``, optional
                ``unit`` / ``drawn_at`` (creatinine).

        Returns:
            Zero or more :class:`LithiumCreatinineTrendAlert` findings. Distinct
            from :class:`LithiumAceiChecker`, :class:`LithiumNsaidChecker`,
            :class:`LithiumThiazideChecker`, and drug-agnostic
            :class:`LabTrendAlertBridge`. Never modifies medications.
        """
        matched: list[tuple[str, str]] = []
        seen: set[str] = set()
        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & _LITHIUM_AGENTS):
                if agent in seen:
                    continue
                matched.append((medication.name, agent))
                seen.add(agent)

        agents = [agent for _med, agent in matched]
        med_names = sorted({med for med, _agent in matched}, key=str.casefold)

        series: list[tuple[str, float]] = []
        for entry in labs or []:
            name = str(entry.get("name", "")).strip().lower()
            if name not in _CREATININE_ALIASES and "creatinine" not in name:
                continue
            try:
                value = float(entry.get("value"))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            drawn = str(entry.get("drawn_at") or "")
            series.append((drawn, value))

        series.sort(key=lambda item: item[0])
        values = [value for _drawn, value in series]
        drawn_ats = [drawn for drawn, _value in series]
        latest = values[-1] if values else None
        percent: float | None = None
        if len(values) >= 2 and values[0] != 0:
            percent = (values[-1] - values[0]) / values[0] * 100.0

        if not agents:
            logger.info("lithium_creatinine_trend_bridge_checked", findings=0)
            return []

        findings: list[LithiumCreatinineTrendAlert] = []

        def _add(kind: str, severity: Severity, rationale: str) -> None:
            findings.append(
                LithiumCreatinineTrendAlert(
                    finding_kind=kind,
                    agents=agents,
                    medication_names=med_names,
                    creatinine_values=values,
                    drawn_ats=drawn_ats,
                    latest_creatinine=latest,
                    percent_change=percent,
                    severity=severity,
                    rationale=rationale,
                )
            )

        rising = len(values) >= 2 and values[-1] > values[0]
        significant_rise = percent is not None and percent >= _MIN_RELATIVE_RISE * 100.0
        elevated = latest is not None and latest >= _ELEVATED_CREATININE
        critical = latest is not None and latest >= _CRITICAL_CREATININE

        if rising and agents:
            sev = Severity.CRITICAL if critical else Severity.HIGH
            _add(
                "rising_creatinine_on_lithium",
                sev,
                (
                    "RESEARCH USE ONLY: Rising creatinine trend on lithium "
                    f"(values {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + f"). Agents: {', '.join(agents)}. Renal-risk bridge "
                    "distinct from LithiumAceiChecker / LithiumNsaidChecker / "
                    "LithiumThiazideChecker and drug-agnostic LabTrendAlertBridge. "
                    "Never modifies medications. Confirm with a qualified "
                    "clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x "
                    "/ Kimi K2."
                ),
            )

        if elevated and agents:
            sev = Severity.CRITICAL if critical else Severity.HIGH
            _add(
                "elevated_creatinine_on_lithium",
                sev,
                (
                    "RESEARCH USE ONLY: Elevated creatinine on lithium "
                    f"(latest {latest}, series {values}). Agents: "
                    f"{', '.join(agents)}. Renal-risk bridge distinct from "
                    "LithiumAceiChecker / LithiumNsaidChecker / "
                    "LithiumThiazideChecker and drug-agnostic LabTrendAlertBridge. "
                    "Never modifies medications. Confirm with a qualified "
                    "clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x "
                    "/ Kimi K2."
                ),
            )

        if (rising or significant_rise or elevated) and agents:
            _add(
                "lithium_renal_risk",
                Severity.CRITICAL if critical else Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Lithium renal-risk advisory for agents "
                    f"{', '.join(agents)} (creatinine {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + "). Distinct from LithiumAceiChecker / LithiumNsaidChecker "
                    "/ LithiumThiazideChecker and LabTrendAlertBridge without "
                    "lithium context. Never modifies medications. Confirm with "
                    "a qualified clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / "
                    "Gemini 3.x / Kimi K2."
                ),
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info("lithium_creatinine_trend_bridge_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
