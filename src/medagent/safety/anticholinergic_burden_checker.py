"""Cumulative anticholinergic-burden safety checker.

Many common medications — sedating antihistamines, tricyclic antidepressants,
bladder antimuscarinics, low-potency antipsychotics — carry anticholinergic
activity. The hazard of any single agent may be modest, but the effect is
*cumulative*: a high total anticholinergic burden is associated with confusion,
falls, urinary retention, and, in older adults, increased cognitive decline.
This is neither a two-agent drug-drug interaction, an allergy, a duplicate
therapy, a pregnancy risk, nor a QT hazard, so the existing checkers do not
surface it.

This checker scores each active medication against the Anticholinergic Cognitive
Burden (ACB) scale (1 = mild, 2 = moderate, 3 = strong) and sums the scores. A
total burden of 3 or more is the established clinically significant threshold, so
every contributing finding's severity is elevated when that threshold is reached.
It uses whole-token matching (never loose substrings), is deterministic, and is
RESEARCH USE ONLY, complementing the drug-drug interaction, drug-allergy,
duplicate-therapy, pregnancy-safety, and QT-prolongation checkers.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import AnticholinergicBurdenRisk, Medication, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Total ACB score at or above which cumulative burden is clinically significant.
_SIGNIFICANT_BURDEN_THRESHOLD: Final[int] = 3

# Canonical anticholinergic agent token -> (ACB score, short descriptor). Agents
# are matched as whole component tokens of a medication name. Scores follow the
# Anticholinergic Cognitive Burden scale (3 = strong, 2 = moderate, 1 = mild).
_ANTICHOLINERGIC_AGENTS: dict[str, tuple[int, str]] = {
    # Score 3 — strong anticholinergics.
    "amitriptyline": (3, "a tricyclic antidepressant"),
    "nortriptyline": (3, "a tricyclic antidepressant"),
    "imipramine": (3, "a tricyclic antidepressant"),
    "doxepin": (3, "a tricyclic antidepressant"),
    "clomipramine": (3, "a tricyclic antidepressant"),
    "diphenhydramine": (3, "a sedating antihistamine"),
    "hydroxyzine": (3, "a sedating antihistamine"),
    "chlorpheniramine": (3, "a sedating antihistamine"),
    "promethazine": (3, "a phenothiazine antihistamine"),
    "meclizine": (3, "a sedating antihistamine"),
    "oxybutynin": (3, "a bladder antimuscarinic"),
    "tolterodine": (3, "a bladder antimuscarinic"),
    "solifenacin": (3, "a bladder antimuscarinic"),
    "dicyclomine": (3, "a gastrointestinal antispasmodic"),
    "hyoscyamine": (3, "a gastrointestinal antispasmodic"),
    "benztropine": (3, "an antiparkinsonian anticholinergic"),
    "scopolamine": (3, "an antimuscarinic"),
    "atropine": (3, "an antimuscarinic"),
    "chlorpromazine": (3, "a low-potency antipsychotic"),
    "clozapine": (3, "an antipsychotic with strong anticholinergic activity"),
    "olanzapine": (3, "an antipsychotic with anticholinergic activity"),
    "quetiapine": (3, "an antipsychotic with anticholinergic activity"),
    "paroxetine": (3, "an SSRI with anticholinergic activity"),
    # Score 2 — moderate anticholinergics.
    "amantadine": (2, "an antiviral/antiparkinsonian agent"),
    "cyclobenzaprine": (2, "a muscle relaxant"),
    "cimetidine": (2, "an H2-receptor antagonist"),
    "loxapine": (2, "an antipsychotic"),
    # Score 1 — mild anticholinergics.
    "ranitidine": (1, "an H2-receptor antagonist"),
    "trazodone": (1, "an antidepressant with mild anticholinergic activity"),
    "alprazolam": (1, "a benzodiazepine with mild anticholinergic activity"),
    "loratadine": (1, "a second-generation antihistamine"),
    "haloperidol": (1, "an antipsychotic with mild anticholinergic activity"),
}


class AnticholinergicBurdenChecker:
    """Flag active medications that contribute to cumulative anticholinergic burden."""

    def check(self, medications: list[Medication]) -> list[AnticholinergicBurdenRisk]:
        """Return one finding per medication with anticholinergic activity.

        Anticholinergic risk is cumulative, so each finding carries the summed
        total burden across all active anticholinergic medications. When the
        total reaches the clinically significant threshold (3), every finding's
        severity is elevated to at least HIGH.

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`AnticholinergicBurdenRisk` per medication matching an
            anticholinergic agent, ordered by descending severity then
            medication name. When a medication matches more than one agent, the
            highest-scoring agent is reported.
        """
        matched: list[tuple[Medication, str, int, str]] = []
        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue
            candidates = [
                (agent, *_ANTICHOLINERGIC_AGENTS[agent])
                for agent in tokens & set(_ANTICHOLINERGIC_AGENTS)
            ]
            if not candidates:
                continue
            agent, score, descriptor = max(candidates, key=lambda item: (item[1], item[0]))
            matched.append((medication, agent, score, descriptor))

        # Cumulative anticholinergic burden is the sum over *distinct* agents,
        # not over raw list entries: the same agent listed twice (common after
        # medication reconciliation or brand/generic double-listing) is a single
        # anticholinergic exposure, so counting each entry would double-count its
        # ACB score and could spuriously cross the significance threshold and
        # over-escalate every finding's severity. Deduplicate by canonical agent
        # (each agent contributes its score once), mirroring the QT checker's
        # distinct-agent concurrency count.
        agent_scores = {agent: score for _med, agent, score, _desc in matched}
        total_burden = sum(agent_scores.values())
        significant = total_burden >= _SIGNIFICANT_BURDEN_THRESHOLD

        findings: list[AnticholinergicBurdenRisk] = []
        for medication, agent, score, descriptor in matched:
            severity = self._baseline_severity(score)
            if significant and _SEVERITY_RANK[severity] < _SEVERITY_RANK[Severity.HIGH]:
                severity = Severity.HIGH
            if significant:
                rationale = (
                    f"Medication '{medication.name}' contains {agent}, {descriptor} with an "
                    f"anticholinergic burden score of {score}. Total anticholinergic burden "
                    f"across active medications is {total_burden} "
                    f"(\u2265{_SIGNIFICANT_BURDEN_THRESHOLD}); cumulative burden raises the risk "
                    "of confusion, falls, and urinary retention — review whether an agent can "
                    "be reduced or substituted."
                )
            else:
                rationale = (
                    f"Medication '{medication.name}' contains {agent}, {descriptor} with an "
                    f"anticholinergic burden score of {score}; total active burden is "
                    f"{total_burden}. Monitor for anticholinergic adverse effects."
                )
            findings.append(
                AnticholinergicBurdenRisk(
                    medication=medication.name,
                    agent=agent,
                    anticholinergic_score=score,
                    total_burden=total_burden,
                    severity=severity,
                    rationale=rationale,
                )
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.medication))
        logger.info(
            "anticholinergic_burden_checked",
            findings=len(findings),
            total_burden=total_burden,
        )
        return findings

    @staticmethod
    def _baseline_severity(score: int) -> Severity:
        """Map a single agent's ACB score to a baseline severity.

        Args:
            score: The agent's anticholinergic burden score (1-3).

        Returns:
            Baseline severity before any cumulative-burden elevation.
        """
        if score >= 3:
            return Severity.MODERATE
        return Severity.LOW

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name.

        Args:
            name: Medication name (may contain brand/dose/component separators).

        Returns:
            Set of component tokens.
        """
        return set(re.findall(r"[a-z0-9]+", name.lower()))
