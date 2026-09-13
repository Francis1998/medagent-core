"""Amiodarone + thyroid lab trend monitoring bridge.

The existing :class:`~medagent.safety.amiodarone_digoxin_checker.AmiodaroneDigoxinChecker`
and :class:`~medagent.safety.amio_warfarin_checker.AmioWarfarinChecker` cover
pairwise DDIs — not TSH/FT4 trend monitoring while on amiodarone.

This bridge fills that gap: it combines amiodarone exposure with abnormal
TSH/FT4 serial trends into advisory
:class:`~medagent.models.AmiodaroneThyroidAlert` findings.
RESEARCH USE ONLY; never modifies medications.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from medagent.logging_config import get_logger
from medagent.models import AmiodaroneThyroidAlert, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_AMIO_AGENTS: Final[frozenset[str]] = frozenset({"amiodarone"})

_TSH_ALIASES: Final[frozenset[str]] = frozenset({"tsh", "thyroid stimulating hormone", "serum tsh"})
_FT4_ALIASES: Final[frozenset[str]] = frozenset(
    {"ft4", "free t4", "free thyroxine", "free-t4", "serum free t4"}
)

_TSH_LOW: Final[float] = 0.4
_TSH_HIGH: Final[float] = 4.5
_FT4_LOW: Final[float] = 0.8
_FT4_HIGH: Final[float] = 1.8
_MIN_RELATIVE_CHANGE: Final[float] = 0.25


class AmiodaroneThyroidBridge:
    """Map amiodarone exposure + TSH/FT4 trends to thyroid monitoring advisories."""

    def check(
        self,
        medications: list[Medication],
        labs: Sequence[Mapping[str, Any]] | None = None,
    ) -> list[AmiodaroneThyroidAlert]:
        """Return amiodarone + thyroid-trend monitoring alerts.

        Args:
            medications: Active medications.
            labs: Optional serial lab draws with ``name``, ``value``, optional
                ``unit`` / ``drawn_at`` (TSH / FT4).

        Returns:
            Zero or more :class:`AmiodaroneThyroidAlert` findings. Distinct from
            :class:`AmiodaroneDigoxinChecker` and :class:`AmioWarfarinChecker`.
            Never modifies medications.
        """
        matched: list[tuple[str, str]] = []
        seen: set[str] = set()
        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & _AMIO_AGENTS):
                if agent in seen:
                    continue
                matched.append((medication.name, agent))
                seen.add(agent)

        agents = [agent for _med, agent in matched]
        med_names = sorted({med for med, _agent in matched}, key=str.casefold)

        tsh_series: list[tuple[str, float]] = []
        ft4_series: list[tuple[str, float]] = []
        for entry in labs or []:
            name = str(entry.get("name", "")).strip().lower()
            try:
                value = float(entry.get("value"))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            drawn = str(entry.get("drawn_at") or "")
            if name in _TSH_ALIASES or name == "tsh":
                tsh_series.append((drawn, value))
            elif name in _FT4_ALIASES or "free t4" in name or name.replace("-", "") == "ft4":
                ft4_series.append((drawn, value))

        tsh_series.sort(key=lambda item: item[0])
        ft4_series.sort(key=lambda item: item[0])
        tsh_values = [value for _drawn, value in tsh_series]
        ft4_values = [value for _drawn, value in ft4_series]
        drawn_ats = sorted({drawn for drawn, _ in tsh_series + ft4_series})
        latest_tsh = tsh_values[-1] if tsh_values else None
        latest_ft4 = ft4_values[-1] if ft4_values else None

        if not agents:
            logger.info("amiodarone_thyroid_bridge_checked", findings=0)
            return []

        findings: list[AmiodaroneThyroidAlert] = []

        def _add(kind: str, severity: Severity, rationale: str) -> None:
            findings.append(
                AmiodaroneThyroidAlert(
                    finding_kind=kind,
                    agents=agents,
                    medication_names=med_names,
                    tsh_values=tsh_values,
                    ft4_values=ft4_values,
                    drawn_ats=drawn_ats,
                    latest_tsh=latest_tsh,
                    latest_ft4=latest_ft4,
                    severity=severity,
                    rationale=rationale,
                )
            )

        rising_tsh = False
        falling_tsh = False
        if len(tsh_values) >= 2:
            start, end = tsh_values[0], tsh_values[-1]
            rel = abs(end - start) / abs(start) if start != 0 else abs(end - start)
            if end > start and (end > _TSH_HIGH or rel >= _MIN_RELATIVE_CHANGE):
                rising_tsh = True
            if end < start and (end < _TSH_LOW or rel >= _MIN_RELATIVE_CHANGE):
                falling_tsh = True

        abnormal_ft4 = False
        if len(ft4_values) >= 2:
            start, end = ft4_values[0], ft4_values[-1]
            rel = abs(end - start) / abs(start) if start != 0 else abs(end - start)
            out_of_band = end < _FT4_LOW or end > _FT4_HIGH
            if end != start and (out_of_band or rel >= _MIN_RELATIVE_CHANGE):
                abnormal_ft4 = True

        if rising_tsh:
            sev = (
                Severity.CRITICAL
                if latest_tsh is not None and latest_tsh >= 10.0
                else Severity.HIGH
            )
            _add(
                "rising_tsh_on_amiodarone",
                sev,
                (
                    "RESEARCH USE ONLY: Rising TSH trend on amiodarone "
                    f"(values {tsh_values}). Agents: {', '.join(agents)}. "
                    "Thyroid monitoring bridge distinct from "
                    "AmiodaroneDigoxinChecker and AmioWarfarinChecker. Never "
                    "modifies medications. Confirm with a qualified clinician; "
                    "prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if falling_tsh:
            sev = (
                Severity.CRITICAL
                if latest_tsh is not None and latest_tsh < _TSH_LOW
                else Severity.HIGH
            )
            _add(
                "falling_tsh_on_amiodarone",
                sev,
                (
                    "RESEARCH USE ONLY: Falling TSH trend on amiodarone "
                    f"(values {tsh_values}). Agents: {', '.join(agents)}. "
                    "Thyroid monitoring bridge distinct from "
                    "AmiodaroneDigoxinChecker and AmioWarfarinChecker. Never "
                    "modifies medications. Confirm with a qualified clinician; "
                    "prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if abnormal_ft4:
            sev = (
                Severity.CRITICAL
                if latest_ft4 is not None and (latest_ft4 < _FT4_LOW or latest_ft4 > _FT4_HIGH)
                else Severity.HIGH
            )
            _add(
                "abnormal_ft4_trend_on_amiodarone",
                sev,
                (
                    "RESEARCH USE ONLY: Abnormal FT4 trend on amiodarone "
                    f"(values {ft4_values}). Agents: {', '.join(agents)}. "
                    "Thyroid monitoring bridge distinct from "
                    "AmiodaroneDigoxinChecker and AmioWarfarinChecker. Never "
                    "modifies medications. Confirm with a qualified clinician; "
                    "prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if rising_tsh or falling_tsh or abnormal_ft4:
            _add(
                "amiodarone_thyroid_monitoring_advisory",
                Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Amiodarone thyroid monitoring advisory "
                    f"for agents {', '.join(agents)} (TSH {tsh_values}, FT4 "
                    f"{ft4_values}). Distinct from AmiodaroneDigoxinChecker and "
                    "AmioWarfarinChecker. Never modifies medications. Confirm "
                    "with a qualified clinician; prefer GPT-5.5 / Claude Sonnet "
                    "4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info("amiodarone_thyroid_bridge_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
