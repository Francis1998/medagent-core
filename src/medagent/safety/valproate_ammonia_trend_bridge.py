"""Valproate + serial ammonia hyperammonemia trend bridge.

The existing
:class:`~medagent.safety.valproate_carbapenem_checker.ValproateCarbapenemChecker`
covers valproate x carbapenem level-drop DDIs, and
:class:`~medagent.safety.lamotrigine_valproate_checker.LamotrigineValproateChecker`
covers lamotrigine x valproate rash/DDI pairs — neither maps valproate
exposure onto rising or elevated serial ammonia (hyperammonemia) trends.

This bridge fills that gap: it combines valproate exposure with rising,
elevated, or clearly critical serial ammonia into advisory
:class:`~medagent.models.ValproateAmmoniaTrendAlert` findings.
RESEARCH USE ONLY; never modifies medications.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, ValproateAmmoniaTrendAlert

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_VALPROATE_AGENTS: Final[frozenset[str]] = frozenset(
    {
        "valproate",
        "valproic",
        "divalproex",
        "depakote",
        "depakene",
    }
)

_AMMONIA_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "ammonia",
        "nh3",
        "serum ammonia",
        "plasma ammonia",
        "ammonia level",
        "blood ammonia",
    }
)

# Advisory ammonia thresholds (umol/L) — RESEARCH USE ONLY, not dosing guidance.
_ELEVATED_AMMONIA: Final[float] = 50.0
_CRITICAL_AMMONIA: Final[float] = 100.0
_MIN_RELATIVE_RISE: Final[float] = 0.25


class ValproateAmmoniaTrendBridge:
    """Map valproate exposure + serial ammonia to hyperammonemia advisories."""

    def check(
        self,
        medications: list[Medication],
        labs: Sequence[Mapping[str, Any]] | None = None,
    ) -> list[ValproateAmmoniaTrendAlert]:
        """Return valproate + ammonia-trend hyperammonemia advisories.

        Args:
            medications: Active medications.
            labs: Optional serial draws with ``name``, ``value``, optional
                ``unit`` / ``drawn_at`` (ammonia).

        Returns:
            Zero or more :class:`ValproateAmmoniaTrendAlert` findings. Distinct
            from :class:`ValproateCarbapenemChecker` and
            :class:`LamotrigineValproateChecker`. Never modifies medications.
        """
        matched: list[tuple[str, str]] = []
        seen: set[str] = set()
        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & _VALPROATE_AGENTS):
                if agent in seen:
                    continue
                matched.append((medication.name, agent))
                seen.add(agent)

        agents = [agent for _med, agent in matched]
        med_names = sorted({med for med, _agent in matched}, key=str.casefold)

        series: list[tuple[str, float]] = []
        for entry in labs or []:
            name = str(entry.get("name", "")).strip().lower()
            looks_like = "ammonia" in name or name == "nh3"
            if name not in _AMMONIA_ALIASES and not looks_like:
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
            logger.info("valproate_ammonia_trend_bridge_checked", findings=0)
            return []

        findings: list[ValproateAmmoniaTrendAlert] = []

        def _add(kind: str, severity: Severity, rationale: str) -> None:
            findings.append(
                ValproateAmmoniaTrendAlert(
                    finding_kind=kind,
                    agents=agents,
                    medication_names=med_names,
                    ammonia_values=values,
                    drawn_ats=drawn_ats,
                    latest_ammonia=latest,
                    percent_change=percent,
                    severity=severity,
                    rationale=rationale,
                )
            )

        rising = len(values) >= 2 and values[-1] > values[0]
        significant_rise = percent is not None and percent >= _MIN_RELATIVE_RISE * 100.0
        elevated = latest is not None and latest >= _ELEVATED_AMMONIA
        critical = latest is not None and latest >= _CRITICAL_AMMONIA

        if (significant_rise or (rising and elevated)) and agents:
            sev = Severity.CRITICAL if critical else Severity.HIGH
            _add(
                "rising_ammonia_on_valproate",
                sev,
                (
                    "RESEARCH USE ONLY: Rising ammonia trend on valproate "
                    f"(values {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + f"). Agents: {', '.join(agents)}. Hyperammonemia bridge "
                    "distinct from ValproateCarbapenemChecker DDI pairs and "
                    "LamotrigineValproateChecker rash/DDI screening. Never "
                    "modifies medications. Confirm with a qualified clinician; "
                    "prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if elevated and agents:
            sev = Severity.CRITICAL if critical else Severity.HIGH
            kind = "critical_ammonia_on_valproate" if critical else "elevated_ammonia_on_valproate"
            _add(
                kind,
                sev,
                (
                    "RESEARCH USE ONLY: "
                    + ("Critical" if critical else "Elevated")
                    + f" ammonia on valproate (latest {latest}, series {values}). "
                    f"Agents: {', '.join(agents)}. Hyperammonemia bridge "
                    "distinct from ValproateCarbapenemChecker and "
                    "LamotrigineValproateChecker. Never modifies medications. "
                    "Confirm with a qualified clinician; prefer GPT-5.5 / "
                    "Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if (significant_rise or elevated) and agents:
            _add(
                "valproate_hyperammonemia_advisory",
                Severity.CRITICAL if critical else Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Valproate hyperammonemia monitoring "
                    f"advisory for agents {', '.join(agents)} (ammonia {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + "). Distinct from ValproateCarbapenemChecker carbapenem "
                    "DDI pairs and LamotrigineValproateChecker. Never modifies "
                    "medications. Confirm with a qualified clinician; prefer "
                    "GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info("valproate_ammonia_trend_bridge_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
