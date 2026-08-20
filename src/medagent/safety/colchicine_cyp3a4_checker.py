"""Colchicine + strong CYP3A4 inhibitor toxicity safety checker.

Strong CYP3A4 inhibitors can markedly increase colchicine exposure and
cause severe or fatal toxicity. The focused inhibitor panel includes
clarithromycin, ketoconazole, itraconazole, and ritonavir.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import ColchicineCyp3a4Risk, Medication, Severity

logger = get_logger(__name__)

_COLCHICINE_AGENTS: Final[dict[str, str]] = {
    "colchicine": "an antigout medication with a narrow therapeutic index",
    "colcrys": "a colchicine brand formulation",
    "mitigare": "a colchicine brand formulation",
    "gloperba": "a colchicine brand formulation",
}

_CYP3A4_INHIBITORS: Final[dict[str, str]] = {
    "clarithromycin": "a macrolide antibiotic and strong CYP3A4 inhibitor",
    "ketoconazole": "an azole antifungal and strong CYP3A4 inhibitor",
    "itraconazole": "an azole antifungal and strong CYP3A4 inhibitor",
    "ritonavir": "an HIV protease inhibitor and strong CYP3A4 inhibitor",
}


class ColchicineCyp3a4Checker:
    """Flag colchicine co-prescribed with strong CYP3A4 inhibitors."""

    def check(self, medications: list[Medication]) -> list[ColchicineCyp3a4Risk]:
        """Return one finding per unique colchicine × inhibitor pair."""
        colchicine_matches: list[tuple[int, Medication, str]] = []
        inhibitor_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            colchicine_candidates = sorted(tokens & set(_COLCHICINE_AGENTS))
            if colchicine_candidates:
                colchicine_matches.append((index, medication, colchicine_candidates[0]))

            inhibitor_candidates = sorted(tokens & set(_CYP3A4_INHIBITORS))
            if inhibitor_candidates:
                inhibitor_matches.append((index, medication, inhibitor_candidates[0]))

        if not colchicine_matches or not inhibitor_matches:
            logger.info("colchicine_cyp3a4_checked", findings=0)
            return []

        colchicine_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        inhibitor_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        findings: list[ColchicineCyp3a4Risk] = []
        seen: set[tuple[str, str]] = set()

        for colchicine_index, colchicine_med, colchicine_agent in colchicine_matches:
            for inhibitor_index, inhibitor_med, inhibitor_agent in inhibitor_matches:
                pair_key = (colchicine_agent, inhibitor_agent)
                if colchicine_index == inhibitor_index or pair_key in seen:
                    continue
                seen.add(pair_key)
                findings.append(
                    ColchicineCyp3a4Risk(
                        medication=colchicine_med.name,
                        agent=colchicine_agent,
                        partner_medication=inhibitor_med.name,
                        partner_agent=inhibitor_agent,
                        severity=Severity.CRITICAL,
                        rationale=self._build_rationale(
                            colchicine_medication=colchicine_med.name,
                            colchicine_agent=colchicine_agent,
                            inhibitor_medication=inhibitor_med.name,
                            inhibitor_agent=inhibitor_agent,
                        ),
                    )
                )

        findings.sort(
            key=lambda finding: (
                finding.medication.lower(),
                finding.partner_medication.lower(),
                finding.agent,
                finding.partner_agent,
            )
        )
        logger.info("colchicine_cyp3a4_checked", findings=len(findings))
        return findings

    @staticmethod
    def _build_rationale(
        *,
        colchicine_medication: str,
        colchicine_agent: str,
        inhibitor_medication: str,
        inhibitor_agent: str,
    ) -> str:
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{colchicine_medication}' contains {colchicine_agent}, "
            f"{_COLCHICINE_AGENTS[colchicine_agent]}, and is co-prescribed "
            f"with '{inhibitor_medication}' ({inhibitor_agent}, "
            f"{_CYP3A4_INHIBITORS[inhibitor_agent]}). Strong CYP3A4 inhibition "
            "can markedly increase colchicine exposure and cause severe or "
            "fatal gastrointestinal, neuromuscular, or bone-marrow toxicity. "
            "Obtain urgent qualified clinical and pharmacist review; do not "
            "change therapy from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", name.lower()))
