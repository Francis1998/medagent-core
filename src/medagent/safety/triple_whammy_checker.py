"""NSAID + ACEI/ARB/ARNI + diuretic "triple whammy" renal risk checker.

Concurrent NSAID, ACE inhibitor / ARB / ARNI, and loop or thiazide diuretic
therapy (the "triple whammy") impairs renal autoregulation and markedly
increases the risk of acute kidney injury. This hazard is distinct from
generic drug-drug interaction screening and single-axis renal dose adjustment.

This checker flags when all three classes are present on the medication list.
It emits one finding per unique NSAID × ACEI/ARB/ARNI × diuretic agent triad
across distinct medication entries, uses whole-token matching (never loose
substrings), and is deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, TripleWhammyRisk

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical NSAID token -> short descriptor.
_NSAID_AGENTS: Final[dict[str, str]] = {
    "ibuprofen": "a nonsteroidal anti-inflammatory drug",
    "naproxen": "a nonsteroidal anti-inflammatory drug",
    "diclofenac": "a nonsteroidal anti-inflammatory drug",
    "ketorolac": "a nonsteroidal anti-inflammatory drug",
    "meloxicam": "a nonsteroidal anti-inflammatory drug",
}

# Canonical ACEI / ARB / ARNI token -> short descriptor.
_ACEI_ARB_ARNI_AGENTS: Final[dict[str, str]] = {
    "lisinopril": "an ACE inhibitor",
    "enalapril": "an ACE inhibitor",
    "ramipril": "an ACE inhibitor",
    "losartan": "an angiotensin receptor blocker",
    "valsartan": "an angiotensin receptor blocker",
    "sacubitril": "an ARNI component (neprilysin inhibitor)",
}

# Canonical loop / thiazide diuretic token -> short descriptor.
_DIURETIC_AGENTS: Final[dict[str, str]] = {
    "furosemide": "a loop diuretic",
    "bumetanide": "a loop diuretic",
    "torsemide": "a loop diuretic",
    "hctz": "a thiazide diuretic (hydrochlorothiazide abbreviation)",
    "hydrochlorothiazide": "a thiazide diuretic",
    "chlorthalidone": "a thiazide-like diuretic",
}


class TripleWhammyChecker:
    """Flag concurrent NSAID + ACEI/ARB/ARNI + loop/thiazide diuretic therapy."""

    def check(self, medications: list[Medication]) -> list[TripleWhammyRisk]:
        """Return findings for each NSAID × ACEI/ARB/ARNI × diuretic triad.

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`TripleWhammyRisk` per unique agent triad across distinct
            medication entries, ordered by descending severity then medication
            names and agents. An empty list is returned when any of the three
            classes is absent.
        """
        nsaid_matches: list[tuple[Medication, str]] = []
        acei_matches: list[tuple[Medication, str]] = []
        diuretic_matches: list[tuple[Medication, str]] = []

        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            nsaid_candidates = sorted(tokens & set(_NSAID_AGENTS))
            if nsaid_candidates:
                nsaid_matches.append((medication, nsaid_candidates[0]))

            acei_candidates = sorted(tokens & set(_ACEI_ARB_ARNI_AGENTS))
            if acei_candidates:
                acei_matches.append((medication, acei_candidates[0]))

            diuretic_candidates = sorted(tokens & set(_DIURETIC_AGENTS))
            if diuretic_candidates:
                diuretic_matches.append((medication, diuretic_candidates[0]))

        if not nsaid_matches or not acei_matches or not diuretic_matches:
            logger.info("triple_whammy_checked", findings=0)
            return []

        findings: list[TripleWhammyRisk] = []
        triad_keys_seen: set[tuple[str, str, str]] = set()

        for nsaid_med, nsaid_agent in nsaid_matches:
            for acei_med, acei_agent in acei_matches:
                for diuretic_med, diuretic_agent in diuretic_matches:
                    triad_key = (nsaid_agent, acei_agent, diuretic_agent)
                    if triad_key in triad_keys_seen:
                        continue
                    triad_keys_seen.add(triad_key)
                    findings.append(
                        TripleWhammyRisk(
                            nsaid_medication=nsaid_med.name,
                            nsaid_agent=nsaid_agent,
                            acei_arb_medication=acei_med.name,
                            acei_arb_agent=acei_agent,
                            diuretic_medication=diuretic_med.name,
                            diuretic_agent=diuretic_agent,
                            severity=Severity.CRITICAL,
                            rationale=self._build_rationale(
                                nsaid_medication=nsaid_med.name,
                                nsaid_agent=nsaid_agent,
                                nsaid_descriptor=_NSAID_AGENTS[nsaid_agent],
                                acei_arb_medication=acei_med.name,
                                acei_arb_agent=acei_agent,
                                acei_arb_descriptor=_ACEI_ARB_ARNI_AGENTS[acei_agent],
                                diuretic_medication=diuretic_med.name,
                                diuretic_agent=diuretic_agent,
                                diuretic_descriptor=_DIURETIC_AGENTS[diuretic_agent],
                            ),
                        )
                    )

        findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK[finding.severity],
                finding.nsaid_medication.lower(),
                finding.acei_arb_medication.lower(),
                finding.diuretic_medication.lower(),
                finding.nsaid_agent,
                finding.acei_arb_agent,
                finding.diuretic_agent,
            )
        )
        logger.info(
            "triple_whammy_checked",
            findings=len(findings),
            nsaid_agents=len({agent for _med, agent in nsaid_matches}),
            acei_arb_agents=len({agent for _med, agent in acei_matches}),
            diuretic_agents=len({agent for _med, agent in diuretic_matches}),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        nsaid_medication: str,
        nsaid_agent: str,
        nsaid_descriptor: str,
        acei_arb_medication: str,
        acei_arb_agent: str,
        acei_arb_descriptor: str,
        diuretic_medication: str,
        diuretic_agent: str,
        diuretic_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY triple-whammy rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{nsaid_medication}' contains {nsaid_agent}, {nsaid_descriptor}; "
            f"'{acei_arb_medication}' contains {acei_arb_agent}, {acei_arb_descriptor}; "
            f"and '{diuretic_medication}' contains {diuretic_agent}, {diuretic_descriptor}. "
            "Concurrent NSAID + ACEI/ARB/ARNI + loop/thiazide diuretic therapy (the "
            "'triple whammy') impairs renal autoregulation and markedly increases acute "
            "kidney injury risk. Review urgently; consider stopping the NSAID and "
            "monitoring renal function and volume status."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
