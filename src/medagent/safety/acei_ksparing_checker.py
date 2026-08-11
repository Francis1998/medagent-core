"""ACE inhibitor/ARB + potassium-sparing therapy hyperkalemia checker.

ACE inhibitors and angiotensin receptor blockers reduce aldosterone activity;
combining either class with a potassium-sparing diuretic or mineralocorticoid
receptor antagonist increases hyperkalemia and renal-function risk. This
hazard is distinct from ACEI + ARB dual-RAAS-blockade duplication and the
triple-whammy acute kidney injury panel.

Whole-token matching is used throughout. Findings are deterministic and
RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import AceiKsparingRisk, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical ACEI/ARB token -> (class, descriptor).
_ACEI_ARB_AGENTS: Final[dict[str, tuple[str, str]]] = {
    "lisinopril": ("ACEI", "an angiotensin-converting enzyme inhibitor"),
    "enalapril": ("ACEI", "an angiotensin-converting enzyme inhibitor"),
    "ramipril": ("ACEI", "an angiotensin-converting enzyme inhibitor"),
    "benazepril": ("ACEI", "an angiotensin-converting enzyme inhibitor"),
    "captopril": ("ACEI", "an angiotensin-converting enzyme inhibitor"),
    "fosinopril": ("ACEI", "an angiotensin-converting enzyme inhibitor"),
    "perindopril": ("ACEI", "an angiotensin-converting enzyme inhibitor"),
    "quinapril": ("ACEI", "an angiotensin-converting enzyme inhibitor"),
    "trandolapril": ("ACEI", "an angiotensin-converting enzyme inhibitor"),
    "losartan": ("ARB", "an angiotensin II receptor blocker"),
    "valsartan": ("ARB", "an angiotensin II receptor blocker"),
    "candesartan": ("ARB", "an angiotensin II receptor blocker"),
    "irbesartan": ("ARB", "an angiotensin II receptor blocker"),
    "olmesartan": ("ARB", "an angiotensin II receptor blocker"),
    "telmisartan": ("ARB", "an angiotensin II receptor blocker"),
    "azilsartan": ("ARB", "an angiotensin II receptor blocker"),
    "eprosartan": ("ARB", "an angiotensin II receptor blocker"),
}

_POTASSIUM_SPARING_AGENTS: Final[dict[str, str]] = {
    "spironolactone": "a mineralocorticoid receptor antagonist",
    "eplerenone": "a mineralocorticoid receptor antagonist",
    "amiloride": "a potassium-sparing epithelial sodium-channel blocker",
    "triamterene": "a potassium-sparing epithelial sodium-channel blocker",
}


class AceiKsparingChecker:
    """Flag ACEI/ARB therapy combined with potassium-sparing agents."""

    def check(self, medications: list[Medication]) -> list[AceiKsparingRisk]:
        """Return one finding per unique ACEI/ARB × potassium-sparing pair.

        Findings are ordered by descending severity, medication names, and
        canonical agents. An empty list is returned when either medication
        class is absent.
        """
        acei_arb_matches: list[tuple[int, Medication, str]] = []
        potassium_sparing_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            acei_arb_candidates = sorted(tokens & set(_ACEI_ARB_AGENTS))
            if acei_arb_candidates:
                acei_arb_matches.append((index, medication, acei_arb_candidates[0]))

            potassium_sparing_candidates = sorted(tokens & set(_POTASSIUM_SPARING_AGENTS))
            if potassium_sparing_candidates:
                potassium_sparing_matches.append(
                    (index, medication, potassium_sparing_candidates[0])
                )

        if not acei_arb_matches or not potassium_sparing_matches:
            logger.info("acei_ksparing_checked", findings=0)
            return []

        acei_arb_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        potassium_sparing_matches.sort(
            key=lambda match: (match[1].name.lower(), match[2], match[0])
        )

        findings: list[AceiKsparingRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for acei_arb_index, acei_arb_med, acei_arb_agent in acei_arb_matches:
            acei_arb_class, acei_arb_desc = _ACEI_ARB_AGENTS[acei_arb_agent]
            for (
                potassium_sparing_index,
                potassium_sparing_med,
                potassium_sparing_agent,
            ) in potassium_sparing_matches:
                if acei_arb_index == potassium_sparing_index:
                    continue
                pair_key = (acei_arb_agent, potassium_sparing_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                findings.append(
                    AceiKsparingRisk(
                        medication=acei_arb_med.name,
                        agent=acei_arb_agent,
                        partner_medication=potassium_sparing_med.name,
                        partner_agent=potassium_sparing_agent,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            acei_arb_medication=acei_arb_med.name,
                            acei_arb_agent=acei_arb_agent,
                            acei_arb_class=acei_arb_class,
                            acei_arb_descriptor=acei_arb_desc,
                            potassium_sparing_medication=potassium_sparing_med.name,
                            potassium_sparing_agent=potassium_sparing_agent,
                            potassium_sparing_descriptor=_POTASSIUM_SPARING_AGENTS[
                                potassium_sparing_agent
                            ],
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
            "acei_ksparing_checked",
            findings=len(findings),
            acei_arb_agents=len({agent for _index, _medication, agent in acei_arb_matches}),
            potassium_sparing_agents=len(
                {agent for _index, _medication, agent in potassium_sparing_matches}
            ),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        acei_arb_medication: str,
        acei_arb_agent: str,
        acei_arb_class: str,
        acei_arb_descriptor: str,
        potassium_sparing_medication: str,
        potassium_sparing_agent: str,
        potassium_sparing_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY hyperkalemia-risk rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{acei_arb_medication}' contains {acei_arb_agent}, "
            f"{acei_arb_descriptor} ({acei_arb_class}), and is co-prescribed with "
            f"'{potassium_sparing_medication}' ({potassium_sparing_agent}, "
            f"{potassium_sparing_descriptor}). Combining ACEI/ARB therapy with a "
            "potassium-sparing agent increases hyperkalemia and renal-function "
            "risk. Promptly review potassium and renal-function monitoring with a "
            "qualified clinician; do not change therapy from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
