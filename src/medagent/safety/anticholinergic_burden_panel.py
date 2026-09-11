"""Anticholinergic burden panel - aggregate ACB stack findings.

The existing :class:`~medagent.safety.anticholinergic_burden_checker.AnticholinergicBurdenChecker`
emits **per-medication** :class:`~medagent.models.AnticholinergicBurdenRisk`
findings with each agent's score and the summed total burden. It does not
produce panel-level aggregate advisory findings keyed by finding kind
(threshold exceeded, high cumulative burden, multi-strong stack).

This panel fills that gap: it aggregates matching ACB agents into advisory
:class:`~medagent.models.AnticholinergicBurdenPanelRisk` findings. Findings
are RESEARCH USE ONLY and never modify medications.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import AnticholinergicBurdenPanelRisk, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Clinically significant cumulative ACB threshold (same scale as the checker).
_ACB_THRESHOLD: Final[int] = 3
# Panel "high burden" floor above the minimum significant threshold.
_HIGH_BURDEN_SCORE: Final[int] = 5
# Strong anticholinergic ACB score.
_STRONG_SCORE: Final[int] = 3

# Canonical anticholinergic agent token -> ACB score (1–3). Whole-token match.
# Mirrors the AnticholinergicBurdenChecker map (not exported from that module).
_ACB_AGENTS: Final[dict[str, int]] = {
    # Score 3 — strong anticholinergics.
    "amitriptyline": 3,
    "nortriptyline": 3,
    "imipramine": 3,
    "doxepin": 3,
    "clomipramine": 3,
    "diphenhydramine": 3,
    "hydroxyzine": 3,
    "chlorpheniramine": 3,
    "promethazine": 3,
    "meclizine": 3,
    "oxybutynin": 3,
    "tolterodine": 3,
    "solifenacin": 3,
    "dicyclomine": 3,
    "hyoscyamine": 3,
    "benztropine": 3,
    "scopolamine": 3,
    "atropine": 3,
    "chlorpromazine": 3,
    "clozapine": 3,
    "olanzapine": 3,
    "quetiapine": 3,
    "paroxetine": 3,
    # Score 2 — moderate anticholinergics.
    "amantadine": 2,
    "cyclobenzaprine": 2,
    "cimetidine": 2,
    "loxapine": 2,
    # Score 1 — mild anticholinergics.
    "ranitidine": 1,
    "trazodone": 1,
    "alprazolam": 1,
    "loratadine": 1,
    "haloperidol": 1,
}


class AnticholinergicBurdenPanel:
    """Aggregate anticholinergic-burden stacks into panel findings."""

    def check(self, medications: list[Medication]) -> list[AnticholinergicBurdenPanelRisk]:
        """Return aggregate ACB-stack findings for the active medication list.

        Args:
            medications: Active patient medications.

        Returns:
            Zero or more :class:`AnticholinergicBurdenPanelRisk` findings
            summarising panel-level ACB stacks. Distinct from per-medication
            :class:`AnticholinergicBurdenChecker` findings. Never modifies
            medications.
        """
        matched: list[tuple[str, str, int]] = []  # (med_name, agent, score)
        seen_agents: set[str] = set()

        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & set(_ACB_AGENTS)):
                if agent in seen_agents:
                    continue
                matched.append((medication.name, agent, _ACB_AGENTS[agent]))
                seen_agents.add(agent)

        if not matched:
            logger.info("anticholinergic_burden_panel_checked", findings=0)
            return []

        agents = [agent for _med, agent, _score in matched]
        agent_scores = {agent: score for _med, agent, score in matched}
        total_acb = sum(agent_scores.values())
        strong_agents = sorted(
            agent for agent, score in agent_scores.items() if score >= _STRONG_SCORE
        )
        all_meds = sorted({med for med, _agent, _score in matched}, key=str.casefold)

        findings: list[AnticholinergicBurdenPanelRisk] = []

        def _add(kind: str, severity: Severity, rationale: str) -> None:
            findings.append(
                AnticholinergicBurdenPanelRisk(
                    finding_kind=kind,
                    agents=agents,
                    total_acb_score=total_acb,
                    medication_names=all_meds,
                    severity=severity,
                    rationale=rationale,
                )
            )

        if total_acb >= _ACB_THRESHOLD:
            threshold_sev = Severity.CRITICAL if total_acb >= _HIGH_BURDEN_SCORE else Severity.HIGH
            _add(
                "acb_threshold_exceeded",
                threshold_sev,
                (
                    "RESEARCH USE ONLY: Anticholinergic burden panel — cumulative "
                    f"ACB score {total_acb} exceeds the clinically significant "
                    f"threshold (≥{_ACB_THRESHOLD}) across agents "
                    f"{', '.join(agents)}. Aggregate panel distinct from "
                    "per-medication AnticholinergicBurdenChecker. Never modifies "
                    "medications. Confirm with a qualified clinician; prefer "
                    "GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if total_acb >= _HIGH_BURDEN_SCORE or (total_acb >= _ACB_THRESHOLD and len(agents) >= 2):
            high_sev = (
                Severity.CRITICAL
                if total_acb >= _HIGH_BURDEN_SCORE or len(strong_agents) >= 2
                else Severity.HIGH
            )
            _add(
                "high_acb_burden",
                high_sev,
                (
                    "RESEARCH USE ONLY: High anticholinergic burden panel — "
                    f"total ACB {total_acb} from {len(agents)} agents "
                    f"({', '.join(agents)}). Panel-level high-burden aggregate "
                    "distinct from per-medication AnticholinergicBurdenChecker. "
                    "Never modifies medications. Confirm with a qualified "
                    "clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x "
                    "/ Kimi K2."
                ),
            )

        if len(strong_agents) >= 2:
            _add(
                "multi_strong_anticholinergic_stack",
                Severity.CRITICAL,
                (
                    "RESEARCH USE ONLY: Multi-strong anticholinergic stack — "
                    f"{len(strong_agents)} score-{_STRONG_SCORE} agents "
                    f"({', '.join(strong_agents)}); total ACB {total_acb}. "
                    "Aggregate panel distinct from per-medication "
                    "AnticholinergicBurdenChecker. Never modifies medications. "
                    "Confirm with a qualified clinician; prefer GPT-5.5 / "
                    "Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info(
            "anticholinergic_burden_panel_checked",
            findings=len(findings),
            total_acb_score=total_acb,
        )
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
