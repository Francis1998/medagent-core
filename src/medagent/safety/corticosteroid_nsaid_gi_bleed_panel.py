"""Systemic corticosteroid + NSAID GI-bleed advisory panel.

The existing
:class:`~medagent.safety.fluoroquinolone_corticosteroid_checker.FluoroquinoloneCorticosteroidChecker`
covers fluoroquinolone × corticosteroid **tendon** risk, and
:class:`~medagent.safety.nsaid_ssri_checker.NsaidSsriBleedChecker` covers
NSAID × SSRI/SNRI bleeding. Neither aggregates systemic corticosteroid + NSAID
gastrointestinal bleeding load at panel level.

This panel fills that gap: it aggregates matching agents into advisory
:class:`~medagent.models.CorticosteroidNsaidGiBleedRisk` findings. Findings are
RESEARCH USE ONLY and never modify medications.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import CorticosteroidNsaidGiBleedRisk, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_CORTICOSTEROIDS: Final[frozenset[str]] = frozenset(
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

_NSAIDS: Final[frozenset[str]] = frozenset(
    {
        "ibuprofen",
        "naproxen",
        "diclofenac",
        "ketorolac",
        "meloxicam",
        "celecoxib",
        "indomethacin",
        "piroxicam",
    }
)


class CorticosteroidNsaidGiBleedPanel:
    """Aggregate systemic corticosteroid + NSAID GI-bleed panel findings."""

    def check(self, medications: list[Medication]) -> list[CorticosteroidNsaidGiBleedRisk]:
        """Return corticosteroid + NSAID GI-bleed panel findings.

        Args:
            medications: Active patient medications.

        Returns:
            Zero or more :class:`CorticosteroidNsaidGiBleedRisk` findings.
            Distinct from tendon-focused
            :class:`FluoroquinoloneCorticosteroidChecker` and
            :class:`NsaidSsriBleedChecker`. Never modifies medications.
        """
        steroids: list[tuple[str, str]] = []
        nsaids: list[tuple[str, str]] = []
        seen_s: set[str] = set()
        seen_n: set[str] = set()

        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & _CORTICOSTEROIDS):
                if agent in seen_s:
                    continue
                steroids.append((medication.name, agent))
                seen_s.add(agent)
            for agent in sorted(tokens & _NSAIDS):
                if agent in seen_n:
                    continue
                nsaids.append((medication.name, agent))
                seen_n.add(agent)

        steroid_agents = [agent for _med, agent in steroids]
        nsaid_agents = [agent for _med, agent in nsaids]
        all_meds = sorted(
            {med for med, _agent in steroids + nsaids},
            key=str.casefold,
        )

        if not steroid_agents or not nsaid_agents:
            logger.info("corticosteroid_nsaid_gi_bleed_panel_checked", findings=0)
            return []

        findings: list[CorticosteroidNsaidGiBleedRisk] = []

        def _add(kind: str, severity: Severity, rationale: str) -> None:
            findings.append(
                CorticosteroidNsaidGiBleedRisk(
                    finding_kind=kind,
                    corticosteroids=steroid_agents,
                    nsaids=nsaid_agents,
                    medication_names=all_meds,
                    severity=severity,
                    rationale=rationale,
                )
            )

        stack_sev = (
            Severity.CRITICAL
            if len(steroid_agents) >= 2 or len(nsaid_agents) >= 2
            else Severity.HIGH
        )
        _add(
            "corticosteroid_nsaid_gi_bleed",
            stack_sev,
            (
                "RESEARCH USE ONLY: Systemic corticosteroid + NSAID GI-bleed "
                f"panel — corticosteroids ({', '.join(steroid_agents)}) with "
                f"NSAIDs ({', '.join(nsaid_agents)}). Concurrent therapy "
                "increases peptic ulcer and GI bleeding risk. Distinct from "
                "FluoroquinoloneCorticosteroidChecker (tendon) and "
                "NsaidSsriBleedChecker. Never modifies medications. Confirm "
                "with a qualified clinician; prefer GPT-5.5 / Claude Sonnet "
                "4.6 / Gemini 3.x / Kimi K2."
            ),
        )

        if len(nsaid_agents) >= 2:
            _add(
                "multi_nsaid_on_corticosteroid",
                Severity.CRITICAL,
                (
                    "RESEARCH USE ONLY: Multiple NSAIDs on systemic "
                    f"corticosteroid(s) {', '.join(steroid_agents)} — NSAIDs "
                    f"{', '.join(nsaid_agents)}. Panel-level multi-NSAID GI "
                    "bleed aggregate distinct from FQ+steroid tendon and "
                    "NSAID+SSRI checkers. Never modifies medications. Confirm "
                    "with a qualified clinician; prefer GPT-5.5 / Claude "
                    "Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if len(steroid_agents) >= 2:
            _add(
                "multi_steroid_nsaid_stack",
                Severity.CRITICAL,
                (
                    "RESEARCH USE ONLY: Multiple systemic corticosteroids with "
                    f"NSAID(s) — steroids ({', '.join(steroid_agents)}) and "
                    f"NSAIDs ({', '.join(nsaid_agents)}). Multi-steroid GI "
                    "bleed stack panel distinct from tendon-focused "
                    "FluoroquinoloneCorticosteroidChecker. Never modifies "
                    "medications. Confirm with a qualified clinician; prefer "
                    "GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info(
            "corticosteroid_nsaid_gi_bleed_panel_checked",
            findings=len(findings),
            corticosteroids=len(steroid_agents),
            nsaids=len(nsaid_agents),
        )
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
