"""Proton-pump inhibitor + methotrexate toxicity safety checker.

PPIs may reduce methotrexate clearance and increase exposure and toxicity risk.
This focused hazard is distinct from methotrexate + NSAID and clopidogrel + PPI
controls. Matching is whole-token based; findings are deterministic and
RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, PpiMtxRisk, Severity

logger = get_logger(__name__)

_MTX_AGENTS: Final[dict[str, str]] = {
    "methotrexate": "an antifolate whose renal clearance may be delayed",
}

_PPI_AGENTS: Final[dict[str, str]] = {
    "omeprazole": "a proton-pump inhibitor",
    "esomeprazole": "a proton-pump inhibitor",
    "pantoprazole": "a proton-pump inhibitor",
    "lansoprazole": "a proton-pump inhibitor",
    "rabeprazole": "a proton-pump inhibitor",
}


class PpiMtxChecker:
    """Flag methotrexate co-prescribed with a supported PPI."""

    def check(self, medications: list[Medication]) -> list[PpiMtxRisk]:
        """Return one finding per unique methotrexate × PPI pair."""
        mtx_matches: list[tuple[int, Medication, str]] = []
        ppi_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue
            mtx_candidates = sorted(tokens & set(_MTX_AGENTS))
            if mtx_candidates:
                mtx_matches.append((index, medication, mtx_candidates[0]))
            ppi_candidates = sorted(tokens & set(_PPI_AGENTS))
            if ppi_candidates:
                ppi_matches.append((index, medication, ppi_candidates[0]))

        if not mtx_matches or not ppi_matches:
            logger.info("ppi_mtx_checked", findings=0)
            return []

        mtx_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        ppi_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        findings: list[PpiMtxRisk] = []
        seen: set[tuple[str, str]] = set()

        for mtx_index, mtx_med, mtx_agent in mtx_matches:
            for ppi_index, ppi_med, ppi_agent in ppi_matches:
                if mtx_index == ppi_index or (mtx_agent, ppi_agent) in seen:
                    continue
                seen.add((mtx_agent, ppi_agent))
                findings.append(
                    PpiMtxRisk(
                        medication=mtx_med.name,
                        agent=mtx_agent,
                        partner_medication=ppi_med.name,
                        partner_agent=ppi_agent,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            mtx_med.name, mtx_agent, ppi_med.name, ppi_agent
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
        logger.info("ppi_mtx_checked", findings=len(findings))
        return findings

    @staticmethod
    def _build_rationale(
        mtx_medication: str,
        mtx_agent: str,
        ppi_medication: str,
        ppi_agent: str,
    ) -> str:
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{mtx_medication}' contains {mtx_agent}, "
            f"{_MTX_AGENTS[mtx_agent]}, and is co-prescribed with "
            f"'{ppi_medication}' ({ppi_agent}, {_PPI_AGENTS[ppi_agent]}). "
            "Proton-pump inhibitors may reduce methotrexate clearance and increase "
            "methotrexate exposure and toxicity risk. Review renal function, toxicity "
            "monitoring, dose context, and alternatives with a qualified clinician; "
            "do not change therapy from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", name.lower()))
