"""Methotrexate + NSAID reduced-clearance toxicity safety checker.

NSAIDs can reduce renal methotrexate elimination and increase methotrexate
exposure, raising risks including myelosuppression, mucositis, renal injury, and
hepatotoxicity. This focused interaction is distinct from methotrexate +
TMP-SMX, lithium + NSAID, and warfarin + NSAID controls.

Whole-token matching is used throughout. Findings are deterministic and
RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, MtxNsaidRisk, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_METHOTREXATE_AGENTS: Final[dict[str, str]] = {
    "methotrexate": "an antifolate with dose- and clearance-dependent toxicity",
}

_NSAID_AGENTS: Final[dict[str, str]] = {
    "ibuprofen": "an NSAID that can reduce renal methotrexate elimination",
    "naproxen": "an NSAID that can reduce renal methotrexate elimination",
    "diclofenac": "an NSAID that can reduce renal methotrexate elimination",
    "indomethacin": "an NSAID associated with marked methotrexate clearance reduction",
    "ketorolac": "a potent NSAID with renal toxicity and clearance concerns",
}


class MtxNsaidChecker:
    """Flag methotrexate co-prescribed with supported NSAIDs."""

    def check(self, medications: list[Medication]) -> list[MtxNsaidRisk]:
        """Return one finding per unique methotrexate × NSAID pair."""
        mtx_matches: list[tuple[int, Medication, str]] = []
        nsaid_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            mtx_candidates = sorted(tokens & set(_METHOTREXATE_AGENTS))
            if mtx_candidates:
                mtx_matches.append((index, medication, mtx_candidates[0]))

            nsaid_candidates = sorted(tokens & set(_NSAID_AGENTS))
            if nsaid_candidates:
                nsaid_matches.append((index, medication, nsaid_candidates[0]))

        if not mtx_matches or not nsaid_matches:
            logger.info("mtx_nsaid_checked", findings=0)
            return []

        mtx_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        nsaid_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))

        findings: list[MtxNsaidRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for mtx_index, mtx_med, mtx_agent in mtx_matches:
            for nsaid_index, nsaid_med, nsaid_agent in nsaid_matches:
                if mtx_index == nsaid_index:
                    continue
                pair_key = (mtx_agent, nsaid_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                findings.append(
                    MtxNsaidRisk(
                        medication=mtx_med.name,
                        agent=mtx_agent,
                        partner_medication=nsaid_med.name,
                        partner_agent=nsaid_agent,
                        severity=self._severity_for(nsaid_agent),
                        rationale=self._build_rationale(
                            mtx_medication=mtx_med.name,
                            mtx_agent=mtx_agent,
                            mtx_descriptor=_METHOTREXATE_AGENTS[mtx_agent],
                            nsaid_medication=nsaid_med.name,
                            nsaid_agent=nsaid_agent,
                            nsaid_descriptor=_NSAID_AGENTS[nsaid_agent],
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
            "mtx_nsaid_checked",
            findings=len(findings),
            mtx_agents=len({agent for _index, _medication, agent in mtx_matches}),
            nsaid_agents=len({agent for _index, _medication, agent in nsaid_matches}),
        )
        return findings

    @staticmethod
    def _severity_for(nsaid_agent: str) -> Severity:
        """Map NSAID partner to advisory severity."""
        if nsaid_agent in {"indomethacin", "ketorolac"}:
            return Severity.CRITICAL
        return Severity.HIGH

    @staticmethod
    def _build_rationale(
        *,
        mtx_medication: str,
        mtx_agent: str,
        mtx_descriptor: str,
        nsaid_medication: str,
        nsaid_agent: str,
        nsaid_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY methotrexate × NSAID rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{mtx_medication}' contains {mtx_agent}, {mtx_descriptor}, "
            f"and is co-prescribed with '{nsaid_medication}' ({nsaid_agent}, "
            f"{nsaid_descriptor}). NSAIDs can reduce renal methotrexate clearance and "
            "increase exposure, raising risks of myelosuppression, mucositis, renal "
            "injury, and hepatotoxicity. Promptly review dose, renal function, CBC, and "
            "the NSAID indication with a qualified clinician; do not change therapy "
            "from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
