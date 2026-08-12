"""ACE inhibitor/ARB + trimethoprim / TMP-SMX hyperkalemia safety checker.

ACE inhibitors and angiotensin receptor blockers reduce aldosterone activity;
trimethoprim (including TMP-SMX / co-trimoxazole) blocks epithelial sodium
channels in a potassium-sparing manner. Concurrent use therefore increases
hyperkalemia risk. This hazard is distinct from ACEI/ARB + potassium-sparing
diuretic hyperkalemia screening and methotrexate + TMP-SMX myelosuppression.

Whole-token matching is used throughout. Findings are deterministic and
RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import AceiTrimethoprimRisk, Medication, Severity

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

# Canonical trimethoprim / TMP-SMX token -> (descriptor, severity).
# Full TMP-SMX brand/generic products escalate to CRITICAL.
_TRIMETHOPRIM_AGENTS: Final[dict[str, tuple[str, Severity]]] = {
    "trimethoprim": (
        "a dihydrofolate-reductase inhibitor with potassium-sparing ENaC blockade",
        Severity.HIGH,
    ),
    "bactrim": (
        "a trimethoprim–sulfamethoxazole (TMP-SMX) brand formulation",
        Severity.CRITICAL,
    ),
    "septra": (
        "a trimethoprim–sulfamethoxazole (TMP-SMX) brand formulation",
        Severity.CRITICAL,
    ),
    "cotrimoxazole": (
        "trimethoprim–sulfamethoxazole (TMP-SMX / co-trimoxazole)",
        Severity.CRITICAL,
    ),
}


class AceiTrimethoprimChecker:
    """Flag ACEI/ARB therapy combined with trimethoprim / TMP-SMX."""

    def check(self, medications: list[Medication]) -> list[AceiTrimethoprimRisk]:
        """Return one finding per unique ACEI/ARB × trimethoprim pair.

        Findings are ordered by descending severity, medication names, and
        canonical agents. An empty list is returned when either medication
        class is absent.
        """
        acei_arb_matches: list[tuple[int, Medication, str]] = []
        trimethoprim_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            acei_arb_candidates = sorted(tokens & set(_ACEI_ARB_AGENTS))
            if acei_arb_candidates:
                acei_arb_matches.append((index, medication, acei_arb_candidates[0]))

            trimethoprim_candidates = sorted(tokens & set(_TRIMETHOPRIM_AGENTS))
            if trimethoprim_candidates:
                trimethoprim_matches.append((index, medication, trimethoprim_candidates[0]))

        if not acei_arb_matches or not trimethoprim_matches:
            logger.info("acei_trimethoprim_checked", findings=0)
            return []

        acei_arb_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        trimethoprim_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))

        findings: list[AceiTrimethoprimRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for acei_arb_index, acei_arb_med, acei_arb_agent in acei_arb_matches:
            acei_arb_class, acei_arb_desc = _ACEI_ARB_AGENTS[acei_arb_agent]
            for (
                trimethoprim_index,
                trimethoprim_med,
                trimethoprim_agent,
            ) in trimethoprim_matches:
                if acei_arb_index == trimethoprim_index:
                    continue
                pair_key = (acei_arb_agent, trimethoprim_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                trimethoprim_desc, severity = _TRIMETHOPRIM_AGENTS[trimethoprim_agent]
                findings.append(
                    AceiTrimethoprimRisk(
                        medication=acei_arb_med.name,
                        agent=acei_arb_agent,
                        partner_medication=trimethoprim_med.name,
                        partner_agent=trimethoprim_agent,
                        severity=severity,
                        rationale=self._build_rationale(
                            acei_arb_medication=acei_arb_med.name,
                            acei_arb_agent=acei_arb_agent,
                            acei_arb_class=acei_arb_class,
                            acei_arb_descriptor=acei_arb_desc,
                            trimethoprim_medication=trimethoprim_med.name,
                            trimethoprim_agent=trimethoprim_agent,
                            trimethoprim_descriptor=trimethoprim_desc,
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
            "acei_trimethoprim_checked",
            findings=len(findings),
            acei_arb_agents=len({agent for _index, _medication, agent in acei_arb_matches}),
            trimethoprim_agents=len({agent for _index, _medication, agent in trimethoprim_matches}),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        acei_arb_medication: str,
        acei_arb_agent: str,
        acei_arb_class: str,
        acei_arb_descriptor: str,
        trimethoprim_medication: str,
        trimethoprim_agent: str,
        trimethoprim_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY hyperkalemia-risk rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{acei_arb_medication}' contains {acei_arb_agent}, "
            f"{acei_arb_descriptor} ({acei_arb_class}), and is co-prescribed with "
            f"'{trimethoprim_medication}' ({trimethoprim_agent}, "
            f"{trimethoprim_descriptor}). Combining ACEI/ARB therapy with "
            "trimethoprim or TMP-SMX increases hyperkalemia risk. Promptly review "
            "potassium and renal-function monitoring with a qualified clinician; "
            "do not change therapy from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
