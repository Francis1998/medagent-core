"""Warfarin + serial INR trend bleeding-risk bridge.

The existing :class:`~medagent.safety.warfarin_nsaid_checker.WarfarinNsaidChecker`
covers pairwise warfarin–NSAID bleeding DDIs, and
:class:`~medagent.safety.lab_trend_alert_bridge.LabTrendAlertBridge` flags
drug-agnostic rising INR — neither requires warfarin context for INR trends.

This bridge fills that gap: it combines warfarin exposure with rising or
supratherapeutic serial INR values into advisory
:class:`~medagent.models.WarfarinInrTrendAlert` findings.
RESEARCH USE ONLY; never modifies medications.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, WarfarinInrTrendAlert

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_WARFARIN_AGENTS: Final[frozenset[str]] = frozenset({"warfarin", "coumadin", "jantoven"})

_INR_ALIASES: Final[frozenset[str]] = frozenset(
    {"inr", "international normalized ratio", "pt/inr", "pt inr"}
)

_SUPRATHERAPEUTIC_INR: Final[float] = 3.0
_CRITICAL_INR: Final[float] = 4.5
_MIN_RELATIVE_RISE: Final[float] = 0.2


class WarfarinInrTrendBridge:
    """Map warfarin exposure + serial INR trends to bleeding-risk advisories."""

    def check(
        self,
        medications: list[Medication],
        labs: Sequence[Mapping[str, Any]] | None = None,
    ) -> list[WarfarinInrTrendAlert]:
        """Return warfarin + INR-trend bleeding-risk alerts.

        Args:
            medications: Active medications.
            labs: Optional serial lab draws with ``name``, ``value``, optional
                ``unit`` / ``drawn_at`` (INR).

        Returns:
            Zero or more :class:`WarfarinInrTrendAlert` findings. Distinct from
            :class:`WarfarinNsaidChecker` and drug-agnostic
            :class:`LabTrendAlertBridge`. Never modifies medications.
        """
        matched: list[tuple[str, str]] = []
        seen: set[str] = set()
        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & _WARFARIN_AGENTS):
                if agent in seen:
                    continue
                matched.append((medication.name, agent))
                seen.add(agent)

        agents = [agent for _med, agent in matched]
        med_names = sorted({med for med, _agent in matched}, key=str.casefold)

        series: list[tuple[str, float]] = []
        for entry in labs or []:
            name = str(entry.get("name", "")).strip().lower()
            if name not in _INR_ALIASES and "inr" not in name:
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
            logger.info("warfarin_inr_trend_bridge_checked", findings=0)
            return []

        findings: list[WarfarinInrTrendAlert] = []

        def _add(kind: str, severity: Severity, rationale: str) -> None:
            findings.append(
                WarfarinInrTrendAlert(
                    finding_kind=kind,
                    agents=agents,
                    medication_names=med_names,
                    inr_values=values,
                    drawn_ats=drawn_ats,
                    latest_inr=latest,
                    percent_change=percent,
                    severity=severity,
                    rationale=rationale,
                )
            )

        rising = len(values) >= 2 and values[-1] > values[0]
        significant_rise = percent is not None and percent >= _MIN_RELATIVE_RISE * 100.0
        supra = latest is not None and latest >= _SUPRATHERAPEUTIC_INR
        critical = latest is not None and latest >= _CRITICAL_INR

        if rising and agents:
            sev = Severity.CRITICAL if critical else Severity.HIGH
            _add(
                "rising_inr_on_warfarin",
                sev,
                (
                    "RESEARCH USE ONLY: Rising INR trend on warfarin "
                    f"(values {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + f"). Agents: {', '.join(agents)}. Bleeding-risk bridge "
                    "distinct from WarfarinNsaidChecker and drug-agnostic "
                    "LabTrendAlertBridge. Never modifies medications. Confirm "
                    "with a qualified clinician; prefer GPT-5.5 / Claude Sonnet "
                    "4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if supra and agents:
            sev = Severity.CRITICAL if critical else Severity.HIGH
            _add(
                "supratherapeutic_inr_on_warfarin",
                sev,
                (
                    "RESEARCH USE ONLY: Supratherapeutic INR on warfarin "
                    f"(latest {latest}, series {values}). Agents: "
                    f"{', '.join(agents)}. Bleeding-risk bridge distinct from "
                    "WarfarinNsaidChecker and drug-agnostic LabTrendAlertBridge. "
                    "Never modifies medications. Confirm with a qualified "
                    "clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x "
                    "/ Kimi K2."
                ),
            )

        if (rising or significant_rise or supra) and agents:
            if not any(
                f.finding_kind in {"rising_inr_on_warfarin", "supratherapeutic_inr_on_warfarin"}
                for f in findings
            ):
                _add(
                    "warfarin_inr_bleeding_risk",
                    Severity.HIGH if rising or supra else Severity.MODERATE,
                    (
                        "RESEARCH USE ONLY: Warfarin exposure "
                        f"({', '.join(agents)}) with serial INR trend {values}. "
                        "Bridge advisory distinct from WarfarinNsaidChecker and "
                        "drug-agnostic LabTrendAlertBridge. Never modifies "
                        "medications. Confirm with a qualified clinician; prefer "
                        "GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                    ),
                )
            else:
                _add(
                    "warfarin_inr_bleeding_risk",
                    Severity.CRITICAL if critical else Severity.HIGH,
                    (
                        "RESEARCH USE ONLY: Warfarin INR bleeding-risk advisory "
                        f"for agents {', '.join(agents)} (INR {values}"
                        + (f", {percent:.1f}%" if percent is not None else "")
                        + "). Distinct from WarfarinNsaidChecker and "
                        "LabTrendAlertBridge without warfarin context. Never "
                        "modifies medications. Confirm with a qualified "
                        "clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini "
                        "3.x / Kimi K2."
                    ),
                )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info("warfarin_inr_trend_bridge_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
