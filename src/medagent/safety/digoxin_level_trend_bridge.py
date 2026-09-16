"""Digoxin + serial serum digoxin level toxicity-trend bridge.

The existing
:class:`~medagent.safety.digoxin_toxicity_checker.DigoxinToxicityChecker`
covers electrolyte / loop-diuretic toxicity cues without serial digoxin levels,
and :class:`~medagent.safety.digoxin_amio_checker.DigoxinAmioChecker` covers
digoxin × amiodarone DDI pairs — neither maps digoxin exposure onto rising or
supratherapeutic serial serum digoxin concentrations.

This bridge fills that gap: it combines digoxin exposure with rising,
elevated, or clearly supratherapeutic serial digoxin levels into advisory
:class:`~medagent.models.DigoxinLevelTrendAlert` findings.
RESEARCH USE ONLY; never modifies medications.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from medagent.logging_config import get_logger
from medagent.models import DigoxinLevelTrendAlert, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_DIGOXIN_AGENTS: Final[frozenset[str]] = frozenset(
    {
        "digoxin",
        "lanoxin",
        "digitek",
        "digox",
    }
)

_DIGOXIN_LEVEL_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "digoxin",
        "digoxin level",
        "serum digoxin",
        "digoxin concentration",
        "digoxin level ng/ml",
        "serum digoxin level",
    }
)

# Advisory digoxin level thresholds (ng/mL) — RESEARCH USE ONLY, not dosing guidance.
_ELEVATED_LEVEL: Final[float] = 1.2
_SUPRATHERAPEUTIC_LEVEL: Final[float] = 2.0
_MIN_RELATIVE_RISE: Final[float] = 0.25


class DigoxinLevelTrendBridge:
    """Map digoxin exposure + serial serum digoxin levels to toxicity cues."""

    def check(
        self,
        medications: list[Medication],
        labs: Sequence[Mapping[str, Any]] | None = None,
    ) -> list[DigoxinLevelTrendAlert]:
        """Return digoxin + serum-level-trend toxicity advisories.

        Args:
            medications: Active medications.
            labs: Optional serial draws with ``name``, ``value``, optional
                ``unit`` / ``drawn_at`` (serum digoxin level).

        Returns:
            Zero or more :class:`DigoxinLevelTrendAlert` findings. Distinct from
            :class:`DigoxinToxicityChecker` and :class:`DigoxinAmioChecker`.
            Never modifies medications.
        """
        matched: list[tuple[str, str]] = []
        seen: set[str] = set()
        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & _DIGOXIN_AGENTS):
                if agent in seen:
                    continue
                matched.append((medication.name, agent))
                seen.add(agent)

        agents = [agent for _med, agent in matched]
        med_names = sorted({med for med, _agent in matched}, key=str.casefold)

        series: list[tuple[str, float]] = []
        for entry in labs or []:
            name = str(entry.get("name", "")).strip().lower()
            looks_like_level = "digoxin" in name and (
                "level" in name or "serum" in name or "concentration" in name
            )
            if name not in _DIGOXIN_LEVEL_ALIASES and not looks_like_level:
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
            logger.info("digoxin_level_trend_bridge_checked", findings=0)
            return []

        findings: list[DigoxinLevelTrendAlert] = []

        def _add(kind: str, severity: Severity, rationale: str) -> None:
            findings.append(
                DigoxinLevelTrendAlert(
                    finding_kind=kind,
                    agents=agents,
                    medication_names=med_names,
                    digoxin_level_values=values,
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
                "rising_digoxin_level",
                sev,
                (
                    "RESEARCH USE ONLY: Rising serum digoxin level trend "
                    f"(values {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + f"). Agents: {', '.join(agents)}. Digoxin-level bridge "
                    "distinct from DigoxinToxicityChecker electrolyte/toxicity "
                    "cues and DigoxinAmioChecker DDI pairs. Never modifies "
                    "medications. Confirm with a qualified clinician; prefer "
                    "GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if elevated and agents:
            sev = Severity.CRITICAL if critical else Severity.HIGH
            kind = "supratherapeutic_digoxin_level" if critical else "elevated_digoxin_level"
            _add(
                kind,
                sev,
                (
                    "RESEARCH USE ONLY: "
                    + ("Supratherapeutic" if critical else "Elevated")
                    + f" serum digoxin level (latest {latest}, series {values}). "
                    f"Agents: {', '.join(agents)}. Digoxin-level bridge distinct "
                    "from DigoxinToxicityChecker and DigoxinAmioChecker. Never "
                    "modifies medications. Confirm with a qualified clinician; "
                    "prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if (significant_rise or elevated) and agents:
            _add(
                "digoxin_level_monitoring_advisory",
                Severity.CRITICAL if critical else Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Digoxin serum-level monitoring advisory "
                    f"for agents {', '.join(agents)} (levels {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + "). Distinct from DigoxinToxicityChecker symptom/electrolyte "
                    "cues and DigoxinAmioChecker amiodarone DDI screening. Never "
                    "modifies medications. Confirm with a qualified clinician; "
                    "prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info("digoxin_level_trend_bridge_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
