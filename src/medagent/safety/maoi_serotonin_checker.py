"""MAOI + serotonergic cross-check safety checker.

Monoamine oxidase inhibitors (MAOIs) are contraindicated with serotonergic
agents — SSRIs, SNRIs, triptans, serotonergic opioids, and others — because
the combination carries a high risk of life-threatening serotonin syndrome. The
existing serotonin-syndrome checker flags any two or more serotonergic agents
co-prescribed; this checker provides a focused MAOI × serotonergic cross-check
that explicitly pairs each MAOI with each concurrent non-MAOI serotonergic
medication, complementing the broader combination logic.

It flags MAOI + SSRI/SNRI/triptan/serotonergic-opioid/etc. combinations with
CRITICAL severity. Whole-token matching is used throughout. Findings are
deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import MaoiSerotoninRisk, Medication, Severity

logger = get_logger(__name__)

_MAOI_CLASS: Final[str] = "MAOI"

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical MAOI token -> short descriptor.
_MAOI_AGENTS: Final[dict[str, str]] = {
    "phenelzine": "a monoamine oxidase inhibitor",
    "tranylcypromine": "a monoamine oxidase inhibitor",
    "isocarboxazid": "a monoamine oxidase inhibitor",
    "selegiline": "a monoamine oxidase inhibitor",
    "rasagiline": "a monoamine oxidase inhibitor",
    "linezolid": "an antibiotic that is a reversible monoamine oxidase inhibitor",
}

# Canonical serotonergic (non-MAOI) token -> (drug class, descriptor).
_SEROTONERGIC_AGENTS: Final[dict[str, tuple[str, str]]] = {
    # SSRIs.
    "fluoxetine": ("SSRI", "a selective serotonin reuptake inhibitor"),
    "sertraline": ("SSRI", "a selective serotonin reuptake inhibitor"),
    "paroxetine": ("SSRI", "a selective serotonin reuptake inhibitor"),
    "citalopram": ("SSRI", "a selective serotonin reuptake inhibitor"),
    "escitalopram": ("SSRI", "a selective serotonin reuptake inhibitor"),
    "fluvoxamine": ("SSRI", "a selective serotonin reuptake inhibitor"),
    # SNRIs.
    "venlafaxine": ("SNRI", "a serotonin-norepinephrine reuptake inhibitor"),
    "desvenlafaxine": ("SNRI", "a serotonin-norepinephrine reuptake inhibitor"),
    "duloxetine": ("SNRI", "a serotonin-norepinephrine reuptake inhibitor"),
    "milnacipran": ("SNRI", "a serotonin-norepinephrine reuptake inhibitor"),
    "levomilnacipran": ("SNRI", "a serotonin-norepinephrine reuptake inhibitor"),
    # Triptans.
    "sumatriptan": ("triptan", "a triptan antimigraine agent"),
    "rizatriptan": ("triptan", "a triptan antimigraine agent"),
    "zolmitriptan": ("triptan", "a triptan antimigraine agent"),
    "eletriptan": ("triptan", "a triptan antimigraine agent"),
    "naratriptan": ("triptan", "a triptan antimigraine agent"),
    # Serotonergic opioids.
    "tramadol": ("opioid", "a serotonergic opioid analgesic"),
    "tapentadol": ("opioid", "a serotonergic opioid analgesic"),
    "meperidine": ("opioid", "a serotonergic opioid analgesic"),
    "methadone": ("opioid", "a serotonergic opioid analgesic"),
    "fentanyl": ("opioid", "a serotonergic opioid analgesic"),
    # Other serotonergic agents.
    "trazodone": ("other", "a serotonergic antidepressant"),
    "mirtazapine": ("other", "a serotonergic antidepressant"),
    "buspirone": ("other", "a serotonergic anxiolytic"),
    "dextromethorphan": ("other", "a serotonergic antitussive"),
    "lithium": ("other", "an agent that potentiates serotonergic activity"),
}


class MaoiSerotoninCrosscheckChecker:
    """Flag MAOI co-prescription with serotonergic medications."""

    def check(self, medications: list[Medication]) -> list[MaoiSerotoninRisk]:
        """Return findings for each MAOI × serotonergic medication pair.

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`MaoiSerotoninRisk` per MAOI × serotonergic pair (both
            directions represented from the MAOI medication's perspective),
            ordered by descending severity then MAOI medication, partner
            medication, and agents. An empty list is returned when no MAOI or
            no serotonergic partner is present.
        """
        maoi_matches: list[tuple[Medication, str]] = []
        serotonergic_matches: list[tuple[Medication, str, str, str]] = []

        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            maoi_candidates = sorted(tokens & set(_MAOI_AGENTS))
            if maoi_candidates:
                maoi_matches.append((medication, maoi_candidates[0]))

            sero_candidates = [
                (agent, *_SEROTONERGIC_AGENTS[agent])
                for agent in sorted(tokens & set(_SEROTONERGIC_AGENTS))
            ]
            if sero_candidates:
                agent, drug_class, descriptor = sero_candidates[0]
                serotonergic_matches.append((medication, agent, drug_class, descriptor))

        if not maoi_matches or not serotonergic_matches:
            logger.info("maoi_serotonin_checked", findings=0)
            return []

        # De-duplicate by distinct agents (not duplicate list entries).
        distinct_maois = {agent for _med, agent in maoi_matches}
        distinct_sero = {agent for _med, agent, _class, _desc in serotonergic_matches}
        if not distinct_maois or not distinct_sero:
            logger.info("maoi_serotonin_checked", findings=0)
            return []

        findings: list[MaoiSerotoninRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for maoi_med, maoi_agent in maoi_matches:
            maoi_desc = _MAOI_AGENTS[maoi_agent]
            for sero_med, sero_agent, sero_class, sero_desc in serotonergic_matches:
                pair_key = (maoi_agent, sero_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                findings.append(
                    MaoiSerotoninRisk(
                        medication=maoi_med.name,
                        agent=maoi_agent,
                        partner_medication=sero_med.name,
                        partner_agent=sero_agent,
                        partner_drug_class=sero_class,
                        severity=Severity.CRITICAL,
                        rationale=self._build_rationale(
                            maoi_medication=maoi_med.name,
                            maoi_agent=maoi_agent,
                            maoi_descriptor=maoi_desc,
                            sero_medication=sero_med.name,
                            sero_agent=sero_agent,
                            sero_descriptor=sero_desc,
                            sero_class=sero_class,
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
            "maoi_serotonin_checked",
            findings=len(findings),
            maoi_agents=len(distinct_maois),
            serotonergic_agents=len(distinct_sero),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        maoi_medication: str,
        maoi_agent: str,
        maoi_descriptor: str,
        sero_medication: str,
        sero_agent: str,
        sero_descriptor: str,
        sero_class: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY MAOI × serotonergic rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{maoi_medication}' contains {maoi_agent}, {maoi_descriptor}, "
            f"and is co-prescribed with '{sero_medication}' ({sero_agent}, {sero_descriptor}, "
            f"{sero_class}). MAOI plus serotonergic agents are contraindicated and carry a "
            "high risk of life-threatening serotonin syndrome. Review urgently and consider "
            "discontinuation or specialist consultation before continuing both agents."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
