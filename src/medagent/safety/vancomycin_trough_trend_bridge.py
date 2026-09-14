"""Vancomycin + serial trough trend toxicity/underdosing bridge.

The existing :class:`~medagent.safety.gentamicin_vancomycin_checker.GentamicinVancomycinChecker`
covers aminoglycoside + vancomycin nephrotoxicity/ototoxicity pairs, and
:class:`~medagent.safety.lab_trend_alert_bridge.LabTrendAlertBridge` is
drug-agnostic — neither combines vancomycin exposure with serial trough trends.

This bridge fills that gap: it maps vancomycin exposure plus high or low serial
trough values into advisory
:class:`~medagent.models.VancomycinTroughTrendAlert` findings.
RESEARCH USE ONLY; never modifies medications.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, VancomycinTroughTrendAlert

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_VANCOMYCIN_AGENTS: Final[frozenset[str]] = frozenset({"vancomycin", "vancocin", "vanco"})

_TROUGH_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "vancomycin trough",
        "vanco trough",
        "vancomycin level",
        "vanco level",
        "trough",
        "vanc trough",
    }
)

# Advisory trough bands (mg/L) — RESEARCH USE ONLY, not dosing guidance.
_LOW_TROUGH: Final[float] = 10.0
_HIGH_TROUGH: Final[float] = 20.0
_CRITICAL_TROUGH: Final[float] = 30.0


class VancomycinTroughTrendBridge:
    """Map vancomycin exposure + serial trough trends to toxicity/underdose cues."""

    def check(
        self,
        medications: list[Medication],
        labs: Sequence[Mapping[str, Any]] | None = None,
    ) -> list[VancomycinTroughTrendAlert]:
        """Return vancomycin + trough-trend advisories.

        Args:
            medications: Active medications.
            labs: Optional serial draws with ``name``, ``value``, optional
                ``unit`` / ``drawn_at`` (vancomycin trough).

        Returns:
            Zero or more :class:`VancomycinTroughTrendAlert` findings. Distinct
            from :class:`GentamicinVancomycinChecker` and drug-agnostic
            :class:`LabTrendAlertBridge`. Never modifies medications.
        """
        matched: list[tuple[str, str]] = []
        seen: set[str] = set()
        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & _VANCOMYCIN_AGENTS):
                if agent in seen:
                    continue
                matched.append((medication.name, agent))
                seen.add(agent)

        agents = [agent for _med, agent in matched]
        med_names = sorted({med for med, _agent in matched}, key=str.casefold)

        series: list[tuple[str, float]] = []
        for entry in labs or []:
            name = str(entry.get("name", "")).strip().lower()
            if name not in _TROUGH_ALIASES and not (
                "trough" in name and ("vanc" in name or "vancomycin" in name)
            ):
                # Accept bare "trough" only when vancomycin is already matched.
                if name != "trough":
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
            logger.info("vancomycin_trough_trend_bridge_checked", findings=0)
            return []

        findings: list[VancomycinTroughTrendAlert] = []

        def _add(kind: str, severity: Severity, rationale: str) -> None:
            findings.append(
                VancomycinTroughTrendAlert(
                    finding_kind=kind,
                    agents=agents,
                    medication_names=med_names,
                    trough_values=values,
                    drawn_ats=drawn_ats,
                    latest_trough=latest,
                    percent_change=percent,
                    severity=severity,
                    rationale=rationale,
                )
            )

        rising = len(values) >= 2 and values[-1] > values[0]
        falling = len(values) >= 2 and values[-1] < values[0]
        high = latest is not None and latest >= _HIGH_TROUGH
        critical_high = latest is not None and latest >= _CRITICAL_TROUGH
        low = latest is not None and latest < _LOW_TROUGH

        if (high or (rising and latest is not None and latest >= _HIGH_TROUGH)) and agents:
            sev = Severity.CRITICAL if critical_high else Severity.HIGH
            _add(
                "supratherapeutic_vancomycin_trough",
                sev,
                (
                    "RESEARCH USE ONLY: Supratherapeutic vancomycin trough "
                    f"(latest {latest}, series {values}). Agents: "
                    f"{', '.join(agents)}. Toxicity-risk bridge distinct from "
                    "GentamicinVancomycinChecker and drug-agnostic "
                    "LabTrendAlertBridge. Never modifies medications. Confirm "
                    "with a qualified clinician; prefer GPT-5.5 / Claude Sonnet "
                    "4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if low and agents:
            _add(
                "subtherapeutic_vancomycin_trough",
                Severity.HIGH if falling or low else Severity.MODERATE,
                (
                    "RESEARCH USE ONLY: Subtherapeutic vancomycin trough "
                    f"(latest {latest}, series {values}). Agents: "
                    f"{', '.join(agents)}. Underdosing-risk bridge distinct from "
                    "GentamicinVancomycinChecker and LabTrendAlertBridge. Never "
                    "modifies medications. Confirm with a qualified clinician; "
                    "prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if rising and high and agents:
            _add(
                "rising_vancomycin_trough",
                Severity.CRITICAL if critical_high else Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Rising vancomycin trough trend "
                    f"(values {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + f"). Agents: {', '.join(agents)}. Toxicity-trend bridge "
                    "distinct from GentamicinVancomycinChecker. Never modifies "
                    "medications. Confirm with a qualified clinician; prefer "
                    "GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if (high or low or (rising and high) or (falling and low)) and agents:
            _add(
                "vancomycin_trough_monitoring_advisory",
                Severity.CRITICAL if critical_high else Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Vancomycin trough monitoring advisory "
                    f"for agents {', '.join(agents)} (trough {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + "). Distinct from GentamicinVancomycinChecker pairwise "
                    "nephrotoxicity and drug-agnostic LabTrendAlertBridge. Never "
                    "modifies medications. Confirm with a qualified clinician; "
                    "prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info("vancomycin_trough_trend_bridge_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
