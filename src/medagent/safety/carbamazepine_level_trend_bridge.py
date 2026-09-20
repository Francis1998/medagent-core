"""Carbamazepine + serial serum carbamazepine level toxicity-trend bridge.

Existing CarbamazepineMacrolideChecker covers macrolide DDI pairs without serial
carbamazepine level trends.

This bridge fills that gap: it combines carbamazepine exposure with rising,
elevated, or clearly supratherapeutic serial carbamazepine levels into advisory
:class:`~medagent.models.CarbamazepineLevelTrendAlert` findings.
RESEARCH USE ONLY; never modifies medications.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from medagent.logging_config import get_logger
from medagent.models import CarbamazepineLevelTrendAlert, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_AGENTS: Final[frozenset[str]] = frozenset(
    {
        "carbamazepine",
        "tegretol",
        "carbatrol",
        "equetro",
    }
)

_LEVEL_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "carbamazepine",
        "carbamazepine level",
        "serum carbamazepine",
        "carbamazepine trough",
        "carbamazepine concentration",
    }
)

# Advisory thresholds (ng/mL) — RESEARCH USE ONLY, not dosing guidance.
_ELEVATED_LEVEL: Final[float] = 12.0
_SUPRATHERAPEUTIC_LEVEL: Final[float] = 15.0
_MIN_RELATIVE_RISE: Final[float] = 0.25


class CarbamazepineLevelTrendBridge:
    """Map cyclosporine exposure + serial serum levels to toxicity cues."""

    def check(
        self,
        medications: list[Medication],
        labs: Sequence[Mapping[str, Any]] | None = None,
    ) -> list[CarbamazepineLevelTrendAlert]:
        """Return carbamazepine + serum-level-trend toxicity advisories.

        Args:
            medications: Active medications.
            labs: Optional serial draws with ``name``, ``value``, optional
                ``unit`` / ``drawn_at``.

        Returns:
            Zero or more :class:`CarbamazepineLevelTrendAlert` findings. Never modifies medications.
        """
        matched: list[tuple[str, str]] = []
        seen: set[str] = set()
        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & _AGENTS):
                if agent in seen:
                    continue
                matched.append((medication.name, agent))
                seen.add(agent)

        agents = [agent for _med, agent in matched]
        med_names = sorted({med for med, _agent in matched}, key=str.casefold)

        series: list[tuple[str, float]] = []
        for entry in labs or []:
            name = str(entry.get("name", "")).strip().lower()
            looks_like_level = "carbamazepine" in name and (
                "level" in name
                or "serum" in name
                or "trough" in name
                or "concentration" in name
            )
            if name not in _LEVEL_ALIASES and not looks_like_level:
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
            logger.info("carbamazepine_level_trend_bridge_checked", findings=0)
            return []

        findings: list[CarbamazepineLevelTrendAlert] = []

        def _add(kind: str, severity: Severity, rationale: str) -> None:
            findings.append(
                CarbamazepineLevelTrendAlert(
                    finding_kind=kind,
                    agents=agents,
                    medication_names=med_names,
                    level_values=values,
                    drawn_ats=drawn_ats,
                    latest_level=latest,
                    percent_change=percent,
                    severity=severity,
                    rationale=rationale,
                )
            )

        rising = len(values) >= 2 and values[-1] > values[0]
        significant_rise = percent is not None and percent >= _MIN_RELATIVE_RISE * 100.0
        elevated = latest is not None and latest >= _ELEVATED_LEVEL
        critical = latest is not None and latest >= _SUPRATHERAPEUTIC_LEVEL

        if (significant_rise or (rising and elevated)) and agents:
            sev = Severity.CRITICAL if critical else Severity.HIGH
            _add(
                "rising_carbamazepine_level",
                sev,
                (
                    "RESEARCH USE ONLY: Rising serum carbamazepine level trend "
                    f"(values {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + f"). Agents: {', '.join(agents)}. Carbamazepine-level bridge "
                    "distinct from related DDI checkers. Never modifies "
                    "medications. Confirm with a qualified clinician; prefer "
                    "GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if elevated and agents:
            sev = Severity.CRITICAL if critical else Severity.HIGH
            kind = (
                "supratherapeutic_carbamazepine_level"
                if critical
                else "elevated_carbamazepine_level"
            )
            _add(
                kind,
                sev,
                (
                    "RESEARCH USE ONLY: "
                    + ("Supratherapeutic" if critical else "Elevated")
                    + f" serum carbamazepine level (latest {latest}, series {values}). "
                    f"Agents: {', '.join(agents)}. Never modifies medications. "
                    "Confirm with a qualified clinician; prefer GPT-5.5 / "
                    "Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if (significant_rise or elevated) and agents:
            _add(
                "carbamazepine_level_monitoring_advisory",
                Severity.CRITICAL if critical else Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Carbamazepine serum-level monitoring advisory "
                    f"for agents {', '.join(agents)} (levels {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + "). Never modifies medications. Confirm with a qualified "
                    "clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / "
                    "Kimi K2."
                ),
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info("carbamazepine_level_trend_bridge_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
