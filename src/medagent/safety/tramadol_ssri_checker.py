"""Tramadol + SSRI/SNRI seizure and serotonin dual-risk safety checker.

Tramadol (and brand Ultram) combined with SSRI or SNRI antidepressants
increases seizure risk and serotonergic toxicity through dual mechanisms —
tramadol lowers the seizure threshold and inhibits serotonin/norepinephrine
reuptake. This hazard is distinct from generic MAOI serotonin cross-checks
and broad serotonin-syndrome screening.

This checker flags tramadol/ultram co-prescribed with SSRI/SNRI partners
(sertraline, fluoxetine, paroxetine, citalopram, escitalopram, venlafaxine,
duloxetine). It emits one finding per unique tramadol × SSRI/SNRI agent pair
across distinct medication entries, uses whole-token matching (never loose
substrings), and is deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, TramadolSsriRisk

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical tramadol token -> short descriptor.
_TRAMADOL_AGENTS: Final[dict[str, str]] = {
    "tramadol": "an opioid analgesic that lowers seizure threshold and is serotonergic",
    "ultram": "a tramadol brand formulation that lowers seizure threshold and is serotonergic",
}

# Canonical SSRI/SNRI token -> (drug class label, short descriptor).
_SSRI_SNRI_AGENTS: Final[dict[str, tuple[str, str]]] = {
    "sertraline": ("SSRI", "a selective serotonin reuptake inhibitor"),
    "fluoxetine": ("SSRI", "a selective serotonin reuptake inhibitor"),
    "paroxetine": ("SSRI", "a selective serotonin reuptake inhibitor"),
    "citalopram": ("SSRI", "a selective serotonin reuptake inhibitor"),
    "escitalopram": ("SSRI", "a selective serotonin reuptake inhibitor"),
    "venlafaxine": ("SNRI", "a serotonin-norepinephrine reuptake inhibitor"),
    "duloxetine": ("SNRI", "a serotonin-norepinephrine reuptake inhibitor"),
}


class TramadolSsriChecker:
    """Flag tramadol co-prescribed with SSRI/SNRI (seizure + serotonin dual risk)."""

    def check(self, medications: list[Medication]) -> list[TramadolSsriRisk]:
        """Return findings for each tramadol × SSRI/SNRI pair.

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`TramadolSsriRisk` per unique tramadol × SSRI/SNRI agent
            pair across distinct medication entries, ordered by descending
            severity then tramadol medication, partner medication, and agents.
            An empty list is returned when tramadol or SSRI/SNRI is absent.
        """
        tramadol_matches: list[tuple[Medication, str]] = []
        ssri_matches: list[tuple[Medication, str]] = []

        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            tramadol_candidates = sorted(tokens & set(_TRAMADOL_AGENTS))
            if tramadol_candidates:
                tramadol_matches.append((medication, tramadol_candidates[0]))

            ssri_candidates = sorted(tokens & set(_SSRI_SNRI_AGENTS))
            if ssri_candidates:
                ssri_matches.append((medication, ssri_candidates[0]))

        if not tramadol_matches or not ssri_matches:
            logger.info("tramadol_ssri_checked", findings=0)
            return []

        findings: list[TramadolSsriRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for tramadol_med, tramadol_agent in tramadol_matches:
            tramadol_desc = _TRAMADOL_AGENTS[tramadol_agent]
            for ssri_med, ssri_agent in ssri_matches:
                pair_key = (tramadol_agent, ssri_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                partner_class, ssri_desc = _SSRI_SNRI_AGENTS[ssri_agent]
                findings.append(
                    TramadolSsriRisk(
                        medication=tramadol_med.name,
                        agent=tramadol_agent,
                        partner_medication=ssri_med.name,
                        partner_agent=ssri_agent,
                        partner_drug_class=partner_class,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            tramadol_medication=tramadol_med.name,
                            tramadol_agent=tramadol_agent,
                            tramadol_descriptor=tramadol_desc,
                            ssri_medication=ssri_med.name,
                            ssri_agent=ssri_agent,
                            ssri_descriptor=ssri_desc,
                            partner_class=partner_class,
                        ),
                    )
                )

        findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK[finding.severity],
                finding.medication.lower(),
                finding.partner_medication.lower(),
                finding.agent,
                finding.partner_agent,
            )
        )
        logger.info(
            "tramadol_ssri_checked",
            findings=len(findings),
            tramadol_agents=len({agent for _med, agent in tramadol_matches}),
            ssri_agents=len({agent for _med, agent in ssri_matches}),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        tramadol_medication: str,
        tramadol_agent: str,
        tramadol_descriptor: str,
        ssri_medication: str,
        ssri_agent: str,
        ssri_descriptor: str,
        partner_class: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY tramadol × SSRI/SNRI rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{tramadol_medication}' contains {tramadol_agent}, "
            f"{tramadol_descriptor}, and is co-prescribed with '{ssri_medication}' "
            f"({ssri_agent}, {ssri_descriptor}, {partner_class}). Concurrent tramadol "
            "with an SSRI/SNRI elevates seizure risk and serotonergic toxicity. "
            "Review urgently; consider non-serotonergic analgesia alternatives and "
            "seizure-risk counseling."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
