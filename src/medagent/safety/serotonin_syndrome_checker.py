"""Serotonin-syndrome safety checker.

Serotonin syndrome is a potentially life-threatening reaction caused by excess
serotonergic activity, most often when two or more serotonergic agents are
combined — for example an SSRI or SNRI with a triptan, tramadol, linezolid, or
another antidepressant. The single most dangerous combination is a monoamine
oxidase inhibitor (MAOI) together with any other serotonergic drug, which is
contraindicated. This hazard depends on the *combination* of agents rather than
a single named drug-drug pair, an allergy, a duplicate therapy, a pregnancy
risk, a QT interval, or cumulative anticholinergic burden, so it is not surfaced
by the existing checkers.

This checker flags each active medication that matches a known serotonergic
agent, but only when two or more serotonergic agents are co-prescribed (a lone
serotonergic drug at a normal dose is not, by itself, serotonin syndrome). When
any MAOI is part of the combination the severity is raised to CRITICAL;
otherwise a multi-agent combination is HIGH. It uses whole-token matching (never
loose substrings), is deterministic, and is RESEARCH USE ONLY, complementing the
drug-drug interaction, drug-allergy, duplicate-therapy, pregnancy-safety,
QT-prolongation, and anticholinergic-burden checkers.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, SerotoninSyndromeRisk, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_MAOI_CLASS: Final[str] = "MAOI"

# Canonical serotonergic agent token -> (drug class, short descriptor). Agents
# are matched as whole component tokens of a medication name. The class drives
# both the rationale and the CRITICAL escalation when a MAOI is present.
_SEROTONERGIC_AGENTS: dict[str, tuple[str, str]] = {
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
    # MAOIs (including the antibiotic linezolid, a reversible MAOI).
    "phenelzine": (_MAOI_CLASS, "a monoamine oxidase inhibitor"),
    "tranylcypromine": (_MAOI_CLASS, "a monoamine oxidase inhibitor"),
    "isocarboxazid": (_MAOI_CLASS, "a monoamine oxidase inhibitor"),
    "selegiline": (_MAOI_CLASS, "a monoamine oxidase inhibitor"),
    "rasagiline": (_MAOI_CLASS, "a monoamine oxidase inhibitor"),
    "linezolid": (_MAOI_CLASS, "an antibiotic that is a reversible monoamine oxidase inhibitor"),
    # Tricyclic antidepressants with strong serotonergic activity.
    "clomipramine": ("TCA", "a serotonergic tricyclic antidepressant"),
    "amitriptyline": ("TCA", "a serotonergic tricyclic antidepressant"),
    "imipramine": ("TCA", "a serotonergic tricyclic antidepressant"),
    # Triptans.
    "sumatriptan": ("triptan", "a triptan antimigraine agent"),
    "rizatriptan": ("triptan", "a triptan antimigraine agent"),
    "zolmitriptan": ("triptan", "a triptan antimigraine agent"),
    "eletriptan": ("triptan", "a triptan antimigraine agent"),
    # Opioids with serotonergic activity.
    "tramadol": ("opioid", "a serotonergic opioid analgesic"),
    "tapentadol": ("opioid", "a serotonergic opioid analgesic"),
    "meperidine": ("opioid", "a serotonergic opioid analgesic"),
    "methadone": ("opioid", "a serotonergic opioid analgesic"),
    "fentanyl": ("opioid", "a serotonergic opioid analgesic"),
    # Other serotonergic agents.
    "trazodone": ("other", "a serotonergic antidepressant"),
    "mirtazapine": ("other", "a serotonergic antidepressant"),
    "buspirone": ("other", "a serotonergic anxiolytic"),
    "ondansetron": ("other", "a serotonergic (5-HT3 antagonist) antiemetic"),
    "dextromethorphan": ("other", "a serotonergic antitussive"),
    "lithium": ("other", "an agent that potentiates serotonergic activity"),
}


class SerotoninSyndromeChecker:
    """Flag co-prescribed serotonergic medications that risk serotonin syndrome."""

    def check(self, medications: list[Medication]) -> list[SerotoninSyndromeRisk]:
        """Return findings when two or more serotonergic agents are co-prescribed.

        Serotonin syndrome arises from the *combination* of serotonergic agents,
        so a lone serotonergic medication yields no finding. When two or more are
        present every finding is at least HIGH, and when any MAOI is part of the
        combination all findings are escalated to CRITICAL (an MAOI plus another
        serotonergic agent is contraindicated).

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`SerotoninSyndromeRisk` per serotonergic medication when
            two or more are present, ordered by descending severity then
            medication name. When a medication matches more than one agent, an
            MAOI match is preferred, otherwise the alphabetically first agent.
            An empty list is returned when fewer than two are present.
        """
        matched: list[tuple[Medication, str, str, str]] = []
        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue
            candidates = [
                (agent, *_SEROTONERGIC_AGENTS[agent])
                for agent in tokens & set(_SEROTONERGIC_AGENTS)
            ]
            if not candidates:
                continue
            # Prefer an MAOI match (it drives the CRITICAL escalation); within the
            # chosen group order deterministically by agent name.
            maoi_candidates = [item for item in candidates if item[1] == _MAOI_CLASS]
            agent, drug_class, descriptor = min(
                maoi_candidates or candidates, key=lambda item: item[0]
            )
            matched.append((medication, agent, drug_class, descriptor))

        # Serotonin syndrome requires a combination; a single agent is not it.
        if len(matched) < 2:
            logger.info("serotonin_syndrome_checked", findings=0)
            return []

        maoi_present = any(drug_class == _MAOI_CLASS for _, _, drug_class, _ in matched)
        combination_severity = Severity.CRITICAL if maoi_present else Severity.HIGH
        concurrent = len(matched) - 1

        findings: list[SerotoninSyndromeRisk] = []
        for medication, agent, drug_class, descriptor in matched:
            if maoi_present:
                rationale = (
                    f"Medication '{medication.name}' contains {agent}, {descriptor}. It is "
                    f"co-prescribed with {concurrent} other serotonergic medication(s), and the "
                    "combination includes a monoamine oxidase inhibitor — an MAOI with another "
                    "serotonergic agent is contraindicated and carries a high risk of "
                    "life-threatening serotonin syndrome. Review urgently."
                )
            else:
                rationale = (
                    f"Medication '{medication.name}' contains {agent}, {descriptor}. It is "
                    f"co-prescribed with {concurrent} other serotonergic medication(s); the "
                    "combination raises the risk of serotonin syndrome — monitor for agitation, "
                    "clonus, hyperthermia, and autonomic instability."
                )
            findings.append(
                SerotoninSyndromeRisk(
                    medication=medication.name,
                    agent=agent,
                    drug_class=drug_class,
                    concurrent_serotonergic_medications=concurrent,
                    severity=combination_severity,
                    rationale=rationale,
                )
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.medication))
        logger.info(
            "serotonin_syndrome_checked",
            findings=len(findings),
            maoi_present=maoi_present,
        )
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name.

        Args:
            name: Medication name (may contain brand/dose/component separators).

        Returns:
            Set of component tokens.
        """
        return set(re.findall(r"[a-z0-9]+", name.lower()))
