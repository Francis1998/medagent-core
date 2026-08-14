"""ACE inhibitor + sacubitril/Entresto angioedema safety checker.

ACE inhibitors must not overlap with sacubitril-containing therapy. A 36-hour
washout is required when switching because concurrent ACE and neprilysin
inhibition substantially increases angioedema risk. This focused
contraindication is distinct from broad ACEI/ARB duplication screening.

Whole-token matching is used throughout. Findings are deterministic and
RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import AceiSacubitrilRisk, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_ACEI_AGENTS: Final[dict[str, str]] = {
    "lisinopril": "an angiotensin-converting enzyme (ACE) inhibitor",
    "enalapril": "an angiotensin-converting enzyme (ACE) inhibitor",
    "ramipril": "an angiotensin-converting enzyme (ACE) inhibitor",
    "benazepril": "an angiotensin-converting enzyme (ACE) inhibitor",
    "quinapril": "an angiotensin-converting enzyme (ACE) inhibitor",
    "captopril": "an angiotensin-converting enzyme (ACE) inhibitor",
    "fosinopril": "an angiotensin-converting enzyme (ACE) inhibitor",
    "perindopril": "an angiotensin-converting enzyme (ACE) inhibitor",
    "trandolapril": "an angiotensin-converting enzyme (ACE) inhibitor",
    "moexipril": "an angiotensin-converting enzyme (ACE) inhibitor",
}

_SACUBITRIL_AGENTS: Final[dict[str, str]] = {
    "sacubitril": "a neprilysin inhibitor, generally administered with valsartan",
    "entresto": "a sacubitril/valsartan (ARNI) brand formulation",
}


class AceiSacubitrilChecker:
    """Flag ACE inhibitors overlapping with sacubitril-containing therapy."""

    def check(self, medications: list[Medication]) -> list[AceiSacubitrilRisk]:
        """Return one finding per unique ACE inhibitor × sacubitril pair."""
        acei_matches: list[tuple[int, Medication, str]] = []
        sacubitril_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            acei_candidates = sorted(tokens & set(_ACEI_AGENTS))
            if acei_candidates:
                acei_matches.append((index, medication, acei_candidates[0]))

            sacubitril_candidates = sorted(tokens & set(_SACUBITRIL_AGENTS))
            if sacubitril_candidates:
                sacubitril_matches.append((index, medication, sacubitril_candidates[0]))

        if not acei_matches or not sacubitril_matches:
            logger.info("acei_sacubitril_checked", findings=0)
            return []

        acei_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        sacubitril_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))

        findings: list[AceiSacubitrilRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for acei_index, acei_med, acei_agent in acei_matches:
            for sacubitril_index, sacubitril_med, sacubitril_agent in sacubitril_matches:
                if acei_index == sacubitril_index:
                    continue
                pair_key = (acei_agent, sacubitril_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                findings.append(
                    AceiSacubitrilRisk(
                        medication=acei_med.name,
                        agent=acei_agent,
                        partner_medication=sacubitril_med.name,
                        partner_agent=sacubitril_agent,
                        severity=Severity.CRITICAL,
                        rationale=self._build_rationale(
                            acei_medication=acei_med.name,
                            acei_agent=acei_agent,
                            acei_descriptor=_ACEI_AGENTS[acei_agent],
                            sacubitril_medication=sacubitril_med.name,
                            sacubitril_agent=sacubitril_agent,
                            sacubitril_descriptor=_SACUBITRIL_AGENTS[sacubitril_agent],
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
            "acei_sacubitril_checked",
            findings=len(findings),
            acei_agents=len({agent for _index, _medication, agent in acei_matches}),
            sacubitril_agents=len({agent for _index, _medication, agent in sacubitril_matches}),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        acei_medication: str,
        acei_agent: str,
        acei_descriptor: str,
        sacubitril_medication: str,
        sacubitril_agent: str,
        sacubitril_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY ACEI × sacubitril rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{acei_medication}' contains {acei_agent}, {acei_descriptor}, "
            f"and overlaps with '{sacubitril_medication}' ({sacubitril_agent}, "
            f"{sacubitril_descriptor}). Concurrent ACE and neprilysin inhibition is "
            "contraindicated because it substantially increases angioedema risk. A "
            "minimum 36-hour washout is required between an ACE inhibitor and "
            "sacubitril-containing therapy. Obtain urgent qualified clinical review; "
            "do not change therapy from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
