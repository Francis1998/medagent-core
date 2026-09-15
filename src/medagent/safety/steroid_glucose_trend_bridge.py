"""Systemic corticosteroid + rising/elevated glucose hyperglycemia bridge.

The existing
:class:`~medagent.safety.corticosteroid_nsaid_gi_bleed_panel.CorticosteroidNsaidGiBleedPanel`
covers corticosteroid + NSAID GI-bleed stacks, and
:class:`~medagent.safety.sglt2_euglycemic_dka_bridge.Sglt2EuglycemicDkaBridge`
pairs SGLT2 inhibitors with low/normal glucose + acidosis cues — neither maps
systemic corticosteroid exposure onto rising or elevated serial glucose.

This bridge fills that gap: it combines corticosteroid exposure with rising or
elevated serial glucose into advisory
:class:`~medagent.models.SteroidGlucoseTrendAlert` findings.
RESEARCH USE ONLY; never modifies medications.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, SteroidGlucoseTrendAlert

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_STEROID_AGENTS: Final[frozenset[str]] = frozenset(
    {
        "prednisone",
        "prednisolone",
        "methylprednisolone",
        "dexamethasone",
        "hydrocortisone",
        "betamethasone",
        "triamcinolone",
        "budesonide",
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
        "fasting glucose",
    }
)

# Advisory thresholds (mg/dL) — RESEARCH USE ONLY, not dosing guidance.
_ELEVATED_GLUCOSE: Final[float] = 180.0
_CRITICAL_GLUCOSE: Final[float] = 300.0
_MIN_RELATIVE_RISE: Final[float] = 0.2


class SteroidGlucoseTrendBridge:
    """Map corticosteroid exposure + serial glucose trends to hyperglycemia advisories."""

    def check(
        self,
        medications: list[Medication],
        labs: Sequence[Mapping[str, Any]] | None = None,
    ) -> list[SteroidGlucoseTrendAlert]:
        """Return steroid + glucose-trend hyperglycemia alerts.

        Args:
            medications: Active medications.
            labs: Optional serial lab draws with ``name``, ``value``, optional
                ``unit`` / ``drawn_at`` (glucose).

        Returns:
            Zero or more :class:`SteroidGlucoseTrendAlert` findings. Distinct
            from :class:`CorticosteroidNsaidGiBleedPanel` and
            :class:`Sglt2EuglycemicDkaBridge`. Never modifies medications.
        """
        matched: list[tuple[str, str]] = []
        seen: set[str] = set()
        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & _STEROID_AGENTS):
                if agent in seen:
                    continue
                matched.append((medication.name, agent))
                seen.add(agent)

        agents = [agent for _med, agent in matched]
        med_names = sorted({med for med, _agent in matched}, key=str.casefold)

        series: list[tuple[str, float]] = []
        for entry in labs or []:
            name = str(entry.get("name", "")).strip().lower()
            if name not in _GLUCOSE_ALIASES and "glucose" not in name:
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
            logger.info("steroid_glucose_trend_bridge_checked", findings=0)
            return []

        findings: list[SteroidGlucoseTrendAlert] = []

        def _add(kind: str, severity: Severity, rationale: str) -> None:
            findings.append(
                SteroidGlucoseTrendAlert(
                    finding_kind=kind,
                    agents=agents,
                    medication_names=med_names,
                    glucose_values=values,
                    drawn_ats=drawn_ats,
                    latest_glucose=latest,
                    percent_change=percent,
                    severity=severity,
                    rationale=rationale,
                )
            )

        rising = len(values) >= 2 and values[-1] > values[0]
        significant_rise = percent is not None and percent >= _MIN_RELATIVE_RISE * 100.0
        elevated = latest is not None and latest >= _ELEVATED_GLUCOSE
        critical = latest is not None and latest >= _CRITICAL_GLUCOSE

        if rising and agents:
            sev = Severity.CRITICAL if critical else Severity.HIGH
            _add(
                "rising_glucose_on_steroid",
                sev,
                (
                    "RESEARCH USE ONLY: Rising glucose trend on corticosteroid "
                    f"(values {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + f"). Agents: {', '.join(agents)}. Hyperglycemia-risk "
                    "bridge distinct from CorticosteroidNsaidGiBleedPanel and "
                    "Sglt2EuglycemicDkaBridge. Never modifies medications. "
                    "Confirm with a qualified clinician; prefer GPT-5.5 / "
                    "Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if elevated and agents:
            sev = Severity.CRITICAL if critical else Severity.HIGH
            _add(
                "elevated_glucose_on_steroid",
                sev,
                (
                    "RESEARCH USE ONLY: Elevated glucose on corticosteroid "
                    f"(latest {latest}, series {values}). Agents: "
                    f"{', '.join(agents)}. Hyperglycemia-risk bridge distinct "
                    "from CorticosteroidNsaidGiBleedPanel and "
                    "Sglt2EuglycemicDkaBridge. Never modifies medications. "
                    "Confirm with a qualified clinician; prefer GPT-5.5 / "
                    "Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if (rising or significant_rise or elevated) and agents:
            _add(
                "steroid_hyperglycemia_advisory",
                Severity.CRITICAL if critical else Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Corticosteroid hyperglycemia advisory "
                    f"for agents {', '.join(agents)} (glucose {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + "). Distinct from CorticosteroidNsaidGiBleedPanel GI "
                    "bleed stacks and Sglt2EuglycemicDkaBridge euglycemic DKA "
                    "cues. Never modifies medications. Confirm with a "
                    "qualified clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / "
                    "Gemini 3.x / Kimi K2."
                ),
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info("steroid_glucose_trend_bridge_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
