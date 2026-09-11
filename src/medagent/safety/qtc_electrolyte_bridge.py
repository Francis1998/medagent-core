"""QTc electrolyte bridge - QT agents + serial K/Mg trend cues.

The existing :class:`~medagent.safety.electrolyte_qt_checker.ElectrolyteQtChecker`
evaluates **point-in-time** potassium/magnesium against QT-prolonging drugs.
:class:`~medagent.safety.qt_prolongation_panel.QtProlongationPanel` aggregates
multi-drug QT load, and
:class:`~medagent.safety.lab_trend_alert_bridge.LabTrendAlertBridge` covers
generic serial-lab trends without QT-agent context.

This bridge fills that gap: it combines QT-prolonging agents with serial K/Mg
draws into advisory :class:`~medagent.models.QTcElectrolyteAlert` findings.
RESEARCH USE ONLY; never modifies medications.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from medagent.logging_config import get_logger
from medagent.models import Medication, QTcElectrolyteAlert, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical QT-prolonging agents (whole-token match). Overlaps the point-in-time
# ElectrolyteQtChecker set plus common CredibleMeds-style cues.
_QT_AGENTS: Final[frozenset[str]] = frozenset(
    {
        "azithromycin",
        "ondansetron",
        "haloperidol",
        "methadone",
        "sotalol",
        "amiodarone",
        "citalopram",
        "escitalopram",
        "dofetilide",
        "droperidol",
        "quinidine",
        "disopyramide",
        "levofloxacin",
        "moxifloxacin",
        "erythromycin",
        "clarithromycin",
        "ziprasidone",
        "thioridazine",
        "pimozide",
        "domperidone",
        "chloroquine",
        "hydroxychloroquine",
        "vandetanib",
        "nilotinib",
    }
)

_K_ALIASES: Final[frozenset[str]] = frozenset(
    {"potassium", "k", "k+", "serum potassium", "plasma potassium"}
)
_MG_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "magnesium",
        "mg",
        "mg++",
        "serum magnesium",
        "plasma magnesium",
        "magnesium level",
    }
)

_LOW_K_MMOL_L: Final[float] = 3.5
_LOW_MG_MG_DL: Final[float] = 1.7


class QTcElectrolyteBridge:
    """Map QT-prolonging agents + serial K/Mg draws to advisory findings."""

    def check(
        self,
        medications: list[Medication],
        labs: Sequence[Mapping[str, Any]] | None = None,
    ) -> list[QTcElectrolyteAlert]:
        """Return QTc + electrolyte trend alerts.

        Args:
            medications: Active medications.
            labs: Optional serial lab draws with ``name``, ``value``, optional
                ``unit`` / ``drawn_at``.

        Returns:
            Zero or more :class:`QTcElectrolyteAlert` findings. Distinct from
            point-in-time :class:`ElectrolyteQtChecker`,
            :class:`QtProlongationPanel`, and non-contextual
            :class:`LabTrendAlertBridge`. Never modifies medications.
        """
        matched: list[str] = []
        seen: set[str] = set()
        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & _QT_AGENTS):
                if agent in seen:
                    continue
                matched.append(agent)
                seen.add(agent)

        if not matched:
            logger.info("qtc_electrolyte_bridge_checked", findings=0)
            return []

        k_series: list[tuple[str, float]] = []
        mg_series: list[tuple[str, float]] = []
        for entry in labs or []:
            name = str(entry.get("name", "")).strip().lower()
            try:
                value = float(entry.get("value"))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            drawn = str(entry.get("drawn_at") or "")
            if name in _K_ALIASES:
                k_series.append((drawn, value))
            elif name in _MG_ALIASES or (
                "magnesium" in name and "oxide" not in name and "citrate" not in name
            ):
                mg_series.append((drawn, value))

        k_series.sort(key=lambda item: item[0])
        mg_series.sort(key=lambda item: item[0])
        k_values = [v for _d, v in k_series]
        mg_values = [v for _d, v in mg_series]
        latest_k = k_values[-1] if k_values else None
        latest_mg = mg_values[-1] if mg_values else None
        falling_k = len(k_values) >= 2 and k_values[-1] < k_values[0]
        falling_mg = len(mg_values) >= 2 and mg_values[-1] < mg_values[0]
        low_k = latest_k is not None and latest_k < _LOW_K_MMOL_L
        low_mg = latest_mg is not None and latest_mg < _LOW_MG_MG_DL

        findings: list[QTcElectrolyteAlert] = []

        def _add(kind: str, severity: Severity, rationale: str) -> None:
            findings.append(
                QTcElectrolyteAlert(
                    finding_kind=kind,
                    agents=matched,
                    k_values=k_values,
                    mg_values=mg_values,
                    severity=severity,
                    rationale=rationale,
                )
            )

        agent_list = ", ".join(matched)

        if falling_k:
            _add(
                "falling_k_on_qt_agent",
                Severity.CRITICAL if low_k else Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Falling potassium trend while on "
                    f"QT-prolonging agents ({agent_list}); K series {k_values}. "
                    "Serial electrolyte bridge distinct from point-in-time "
                    "ElectrolyteQtChecker, QtProlongationPanel, and "
                    "LabTrendAlertBridge. Never modifies medications. Confirm "
                    "with a qualified clinician; prefer GPT-5.5 / Claude Sonnet "
                    "4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if falling_mg:
            _add(
                "falling_mg_on_qt_agent",
                Severity.CRITICAL if low_mg else Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Falling magnesium trend while on "
                    f"QT-prolonging agents ({agent_list}); Mg series {mg_values}. "
                    "Serial electrolyte bridge distinct from point-in-time "
                    "ElectrolyteQtChecker. Never modifies medications. Confirm "
                    "with a qualified clinician; prefer GPT-5.5 / Claude Sonnet "
                    "4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if low_k:
            _add(
                "low_k_on_qt_agent",
                Severity.CRITICAL,
                (
                    "RESEARCH USE ONLY: Latest potassium "
                    f"{latest_k} mmol/L below {_LOW_K_MMOL_L} while on "
                    f"QT-prolonging agents ({agent_list}). Distinct from "
                    "point-in-time ElectrolyteQtChecker single-draw path and "
                    "LabTrendAlertBridge rising-K cue. Never modifies "
                    "medications. Confirm with a qualified clinician; prefer "
                    "GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if low_mg:
            _add(
                "low_mg_on_qt_agent",
                Severity.CRITICAL,
                (
                    "RESEARCH USE ONLY: Latest magnesium "
                    f"{latest_mg} mg/dL below {_LOW_MG_MG_DL} while on "
                    f"QT-prolonging agents ({agent_list}). Distinct from "
                    "point-in-time ElectrolyteQtChecker. Never modifies "
                    "medications. Confirm with a qualified clinician; prefer "
                    "GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if len(matched) >= 2 and (falling_k or falling_mg or low_k or low_mg):
            _add(
                "multi_qt_agent_electrolyte_risk",
                Severity.CRITICAL,
                (
                    "RESEARCH USE ONLY: Multi QT-prolonging agent stack "
                    f"({agent_list}) with adverse K/Mg serial cues "
                    f"(K={k_values}, Mg={mg_values}). Aggregate bridge "
                    "distinct from QtProlongationPanel drug-count findings. "
                    "Never modifies medications. Confirm with a qualified "
                    "clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini "
                    "3.x / Kimi K2."
                ),
            )

        findings.sort(key=lambda f: (-_SEVERITY_RANK[f.severity], f.finding_kind))
        logger.info("qtc_electrolyte_bridge_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
