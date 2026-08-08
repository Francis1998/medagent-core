"""ACEI + ARB + ARNI dual-blockade duplication safety checker.

Concurrent therapy with two or more distinct renin–angiotensin system classes
— ACE inhibitors, angiotensin receptor blockers (ARBs), and ARNIs — produces
dual RAAS blockade with excess hyperkalemia, hypotension, and renal risk
without outcome benefit. This hazard is distinct from the triple-whammy
(NSAID + ACEI/ARB + diuretic) check and generic drug-drug interaction
screening.

This checker flags when ≥2 distinct classes among ACEI (lisinopril, enalapril,
ramipril), ARB (losartan, valsartan, olmesartan), and ARNI (sacubitril) appear
together. It emits one finding per unique cross-class agent pair, uses
whole-token matching (never loose substrings), and is deterministic and
RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import AceiArbDuplicationRisk, Medication, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical agent token -> (RAAS class label, short descriptor).
_ACEI_AGENTS: Final[dict[str, str]] = {
    "lisinopril": "an ACE inhibitor",
    "enalapril": "an ACE inhibitor",
    "ramipril": "an ACE inhibitor",
}

_ARB_AGENTS: Final[dict[str, str]] = {
    "losartan": "an angiotensin receptor blocker",
    "valsartan": "an angiotensin receptor blocker",
    "olmesartan": "an angiotensin receptor blocker",
}

_ARNI_AGENTS: Final[dict[str, str]] = {
    "sacubitril": "an ARNI component (neprilysin inhibitor; typically with valsartan)",
}

_CLASS_PANELS: Final[dict[str, dict[str, str]]] = {
    "ACEI": _ACEI_AGENTS,
    "ARB": _ARB_AGENTS,
    "ARNI": _ARNI_AGENTS,
}


class AceiArbDuplicationChecker:
    """Flag dual RAAS blockade when ≥2 of ACEI, ARB, and ARNI classes co-occur."""

    def check(self, medications: list[Medication]) -> list[AceiArbDuplicationRisk]:
        """Return findings for each cross-class ACEI/ARB/ARNI agent pair.

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`AceiArbDuplicationRisk` per unique cross-class agent
            pair across distinct medication entries, ordered by descending
            severity then medication names and agents. An empty list is
            returned when fewer than two distinct RAAS classes are present.
        """
        # Matches grouped by class: class -> list of (medication, agent).
        class_matches: dict[str, list[tuple[Medication, str]]] = {
            "ACEI": [],
            "ARB": [],
            "ARNI": [],
        }

        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            for class_label, panel in _CLASS_PANELS.items():
                candidates = sorted(tokens & set(panel))
                if candidates:
                    class_matches[class_label].append((medication, candidates[0]))

        present_classes = [label for label, matches in class_matches.items() if matches]
        if len(present_classes) < 2:
            logger.info("acei_arb_duplication_checked", findings=0)
            return []

        # CRITICAL when ACEI+ARB (classic dual blockade, ± ARNI);
        # HIGH for ACEI/ARB + ARNI two-class combinations without ACEI+ARB.
        has_acei_arb = bool(class_matches["ACEI"]) and bool(class_matches["ARB"])
        severity = Severity.CRITICAL if has_acei_arb else Severity.HIGH

        findings: list[AceiArbDuplicationRisk] = []
        pair_keys_seen: set[tuple[str, str, str, str]] = set()

        # Emit one finding per ordered cross-class pair (class_a < class_b by name).
        ordered_classes = sorted(present_classes)
        for i, class_a in enumerate(ordered_classes):
            for class_b in ordered_classes[i + 1 :]:
                for med_a, agent_a in class_matches[class_a]:
                    for med_b, agent_b in class_matches[class_b]:
                        pair_key = (class_a, agent_a, class_b, agent_b)
                        if pair_key in pair_keys_seen:
                            continue
                        pair_keys_seen.add(pair_key)
                        findings.append(
                            AceiArbDuplicationRisk(
                                medication_a=med_a.name,
                                agent_a=agent_a,
                                class_a=class_a,
                                medication_b=med_b.name,
                                agent_b=agent_b,
                                class_b=class_b,
                                classes_present=sorted(present_classes),
                                severity=severity,
                                rationale=self._build_rationale(
                                    medication_a=med_a.name,
                                    agent_a=agent_a,
                                    class_a=class_a,
                                    descriptor_a=_CLASS_PANELS[class_a][agent_a],
                                    medication_b=med_b.name,
                                    agent_b=agent_b,
                                    class_b=class_b,
                                    descriptor_b=_CLASS_PANELS[class_b][agent_b],
                                    classes_present=sorted(present_classes),
                                ),
                            )
                        )

        findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK[finding.severity],
                finding.medication_a.lower(),
                finding.medication_b.lower(),
                finding.agent_a,
                finding.agent_b,
            )
        )
        logger.info(
            "acei_arb_duplication_checked",
            findings=len(findings),
            classes=sorted(present_classes),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        medication_a: str,
        agent_a: str,
        class_a: str,
        descriptor_a: str,
        medication_b: str,
        agent_b: str,
        class_b: str,
        descriptor_b: str,
        classes_present: list[str],
    ) -> str:
        """Compose a RESEARCH USE ONLY ACEI/ARB/ARNI dual-blockade rationale."""
        class_list = " + ".join(classes_present)
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{medication_a}' contains {agent_a}, {descriptor_a} "
            f"({class_a}), and is co-prescribed with '{medication_b}' "
            f"({agent_b}, {descriptor_b}, {class_b}). Concurrent therapy across "
            f"distinct RAAS classes ({class_list}) produces dual blockade with "
            "excess hyperkalemia, hypotension, and renal risk without outcome "
            "benefit. Review urgently and avoid combining ACEI, ARB, and/or ARNI."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
