"""Lithium + serial TSH thyroid-monitoring trend bridge.

The existing
:class:`~medagent.safety.lithium_creatinine_trend_bridge.LithiumCreatinineTrendBridge`
covers lithium + creatinine renal-risk trends, and
:class:`~medagent.safety.amiodarone_thyroid_bridge.AmiodaroneThyroidBridge`
covers amiodarone + TSH/FT4 thyroid monitoring — neither maps lithium
exposure onto serial TSH thyroid trends.

This bridge fills that gap: it combines lithium exposure with rising,
falling, or clearly abnormal serial TSH into advisory
:class:`~medagent.models.LithiumTshTrendAlert` findings.
RESEARCH USE ONLY; never modifies medications.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from medagent.logging_config import get_logger
from medagent.models import LithiumTshTrendAlert, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_LITHIUM_AGENTS: Final[frozenset[str]] = frozenset({"lithium", "lithobid", "eskalith"})

_TSH_ALIASES: Final[frozenset[str]] = frozenset(
    {"tsh", "thyroid stimulating hormone", "serum tsh", "tsh level"}
)

# Advisory TSH thresholds (mIU/L) — RESEARCH USE ONLY, not dosing guidance.
_TSH_LOW: Final[float] = 0.4
_TSH_HIGH: Final[float] = 4.5
_TSH_CRITICAL_HIGH: Final[float] = 10.0
_MIN_RELATIVE_CHANGE: Final[float] = 0.25


class LithiumTshTrendBridge:
    """Map lithium exposure + serial TSH trends to thyroid-monitoring advisories."""

    def check(
        self,
        medications: list[Medication],
        labs: Sequence[Mapping[str, Any]] | None = None,
    ) -> list[LithiumTshTrendAlert]:
        """Return lithium + TSH-trend thyroid-monitoring alerts.

        Args:
            medications: Active medications.
            labs: Optional serial draws with ``name``, ``value``, optional
                ``unit`` / ``drawn_at`` (TSH).

        Returns:
            Zero or more :class:`LithiumTshTrendAlert` findings. Distinct from
            :class:`LithiumCreatinineTrendBridge` and
            :class:`AmiodaroneThyroidBridge`. Never modifies medications.
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
            if name not in _TSH_ALIASES and name != "tsh" and "tsh" not in name:
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
            logger.info("lithium_tsh_trend_bridge_checked", findings=0)
            return []

        findings: list[LithiumTshTrendAlert] = []

        def _add(kind: str, severity: Severity, rationale: str) -> None:
            findings.append(
                LithiumTshTrendAlert(
                    finding_kind=kind,
                    agents=agents,
                    medication_names=med_names,
                    tsh_values=values,
                    drawn_ats=drawn_ats,
                    latest_tsh=latest,
                    percent_change=percent,
                    severity=severity,
                    rationale=rationale,
                )
            )

        rising_tsh = False
        falling_tsh = False
        if len(values) >= 2:
            start, end = values[0], values[-1]
            rel = abs(end - start) / abs(start) if start != 0 else abs(end - start)
            if end > start and (end > _TSH_HIGH or rel >= _MIN_RELATIVE_CHANGE):
                rising_tsh = True
            if end < start and (end < _TSH_LOW or rel >= _MIN_RELATIVE_CHANGE):
                falling_tsh = True

        elevated = latest is not None and latest >= _TSH_HIGH
        critical_high = latest is not None and latest >= _TSH_CRITICAL_HIGH
        low = latest is not None and latest < _TSH_LOW

        if rising_tsh and agents:
            sev = Severity.CRITICAL if critical_high else Severity.HIGH
            _add(
                "rising_tsh_on_lithium",
                sev,
                (
                    "RESEARCH USE ONLY: Rising TSH trend on lithium "
                    f"(values {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + f"). Agents: {', '.join(agents)}. Thyroid-monitoring "
                    "bridge distinct from LithiumCreatinineTrendBridge renal "
                    "creatinine trends and AmiodaroneThyroidBridge amiodarone "
                    "context. Never modifies medications. Confirm with a "
                    "qualified clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / "
                    "Gemini 3.x / Kimi K2."
                ),
            )

        if falling_tsh and agents:
            sev = Severity.CRITICAL if low else Severity.HIGH
            _add(
                "falling_tsh_on_lithium",
                sev,
                (
                    "RESEARCH USE ONLY: Falling TSH trend on lithium "
                    f"(values {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + f"). Agents: {', '.join(agents)}. Thyroid-monitoring "
                    "bridge distinct from LithiumCreatinineTrendBridge and "
                    "AmiodaroneThyroidBridge. Never modifies medications. "
                    "Confirm with a qualified clinician; prefer GPT-5.5 / "
                    "Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if elevated and agents:
            sev = Severity.CRITICAL if critical_high else Severity.HIGH
            _add(
                "elevated_tsh_on_lithium",
                sev,
                (
                    "RESEARCH USE ONLY: Elevated TSH on lithium "
                    f"(latest {latest}, series {values}). Agents: "
                    f"{', '.join(agents)}. Thyroid-monitoring bridge distinct "
                    "from LithiumCreatinineTrendBridge and "
                    "AmiodaroneThyroidBridge. Never modifies medications. "
                    "Confirm with a qualified clinician; prefer GPT-5.5 / "
                    "Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if (rising_tsh or falling_tsh or elevated) and agents:
            _add(
                "lithium_tsh_monitoring_advisory",
                Severity.CRITICAL if critical_high or low else Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Lithium TSH thyroid-monitoring advisory "
                    f"for agents {', '.join(agents)} (TSH {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + "). Distinct from LithiumCreatinineTrendBridge creatinine "
                    "renal-risk cues and AmiodaroneThyroidBridge amiodarone "
                    "TSH/FT4 monitoring. Never modifies medications. Confirm "
                    "with a qualified clinician; prefer GPT-5.5 / Claude Sonnet "
                    "4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info("lithium_tsh_trend_bridge_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
