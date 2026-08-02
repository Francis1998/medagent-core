"""Digoxin toxicity risk safety checker.

Hypokalemia and hypomagnesemia increase digoxin toxicity risk by enhancing
binding to the Na+/K+-ATPase. Loop diuretics promote electrolyte losses and
compound this hazard when potassium or magnesium repletion is not documented.

This checker flags digoxin when potassium or magnesium is below conservative
thresholds, or when a loop diuretic is co-prescribed without K/Mg repletion
cues on the medication list. Whole-token matching is used throughout. Findings
are deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import DigoxinToxicityRisk, Medication, Severity

logger = get_logger(__name__)

_POTASSIUM_LOW_THRESHOLD_MMOL_L: Final[float] = 3.5
_MAGNESIUM_LOW_THRESHOLD_MG_DL: Final[float] = 1.7

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_FINDING_KIND_RANK: Final[dict[str, int]] = {
    "low_potassium": 0,
    "low_magnesium": 1,
    "loop_diuretic_without_repletion": 2,
}

_DIGOXIN_AGENTS: Final[dict[str, str]] = {
    "digoxin": "a cardiac glycoside with narrow therapeutic index",
}

_LOOP_DIURETICS: Final[dict[str, str]] = {
    "furosemide": "a loop diuretic that promotes potassium and magnesium loss",
    "bumetanide": "a loop diuretic that promotes potassium and magnesium loss",
    "torsemide": "a loop diuretic that promotes potassium and magnesium loss",
}

# Agents suggesting documented K/Mg repletion or potassium-sparing therapy.
_REPLETION_AGENTS: Final[dict[str, str]] = {
    "potassium": "a potassium supplement",
    "kcl": "a potassium chloride supplement",
    "magnesium": "a magnesium supplement",
    "spironolactone": "a potassium-sparing diuretic",
    "eplerenone": "a potassium-sparing mineralocorticoid antagonist",
    "amiloride": "a potassium-sparing diuretic",
    "triamterene": "a potassium-sparing diuretic",
}


class DigoxinToxicityChecker:
    """Flag digoxin when electrolyte status or loop diuretic use elevates toxicity risk."""

    def check(
        self,
        medications: list[Medication],
        potassium_mmol_l: float | None = None,
        magnesium_mg_dl: float | None = None,
    ) -> list[DigoxinToxicityRisk]:
        """Return findings for digoxin with elevated toxicity risk.

        Args:
            medications: Active patient medications.
            potassium_mmol_l: Serum potassium in mmol/L, or None when unknown.
            magnesium_mg_dl: Serum magnesium in mg/dL, or None when unknown.

        Returns:
            One :class:`DigoxinToxicityRisk` per digoxin medication per applicable
            finding kind, ordered by descending severity then medication name and
            finding kind. An empty list is returned when no digoxin is present or
            no toxicity risk factors apply.
        """
        digoxin_matches: list[tuple[Medication, str]] = []
        loop_diuretic_agents_found: set[str] = set()
        repletion_agents_found: set[str] = set()

        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            digoxin_candidates = sorted(tokens & set(_DIGOXIN_AGENTS))
            if digoxin_candidates:
                digoxin_matches.append((medication, digoxin_candidates[0]))

            loop_diuretic_agents_found.update(tokens & set(_LOOP_DIURETICS))
            repletion_agents_found.update(tokens & set(_REPLETION_AGENTS))

        if not digoxin_matches:
            logger.info("digoxin_toxicity_checked", findings=0)
            return []

        finding_kinds = self._toxicity_finding_kinds(
            potassium_mmol_l=potassium_mmol_l,
            magnesium_mg_dl=magnesium_mg_dl,
            loop_diuretic_agents_found=loop_diuretic_agents_found,
            repletion_agents_found=repletion_agents_found,
        )
        if not finding_kinds:
            logger.info("digoxin_toxicity_checked", findings=0, digoxin_agents=len(digoxin_matches))
            return []

        findings: list[DigoxinToxicityRisk] = []
        sorted_loop = sorted(loop_diuretic_agents_found)
        sorted_repletion = sorted(repletion_agents_found)

        for medication, agent in digoxin_matches:
            descriptor = _DIGOXIN_AGENTS[agent]
            for finding_kind in finding_kinds:
                findings.append(
                    DigoxinToxicityRisk(
                        medication=medication.name,
                        agent=agent,
                        finding_kind=finding_kind,
                        severity=self._severity_for_kind(finding_kind),
                        potassium_mmol_l=potassium_mmol_l,
                        magnesium_mg_dl=magnesium_mg_dl,
                        loop_diuretic_agents_found=sorted_loop,
                        repletion_agents_found=sorted_repletion,
                        rationale=self._build_rationale(
                            medication_name=medication.name,
                            agent=agent,
                            descriptor=descriptor,
                            finding_kind=finding_kind,
                            potassium_mmol_l=potassium_mmol_l,
                            magnesium_mg_dl=magnesium_mg_dl,
                            loop_diuretic_agents_found=sorted_loop,
                            repletion_agents_found=sorted_repletion,
                        ),
                    )
                )

        findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK[finding.severity],
                finding.medication.lower(),
                _FINDING_KIND_RANK[finding.finding_kind],
                finding.agent,
            )
        )
        logger.info(
            "digoxin_toxicity_checked",
            findings=len(findings),
            digoxin_agents=len(digoxin_matches),
            finding_kinds=finding_kinds,
        )
        return findings

    @staticmethod
    def _toxicity_finding_kinds(
        *,
        potassium_mmol_l: float | None,
        magnesium_mg_dl: float | None,
        loop_diuretic_agents_found: set[str],
        repletion_agents_found: set[str],
    ) -> list[str]:
        """Return applicable finding kinds for digoxin toxicity risk."""
        kinds: list[str] = []
        if potassium_mmol_l is not None and potassium_mmol_l < _POTASSIUM_LOW_THRESHOLD_MMOL_L:
            kinds.append("low_potassium")
        if magnesium_mg_dl is not None and magnesium_mg_dl < _MAGNESIUM_LOW_THRESHOLD_MG_DL:
            kinds.append("low_magnesium")
        if loop_diuretic_agents_found and not repletion_agents_found:
            kinds.append("loop_diuretic_without_repletion")
        return kinds

    @staticmethod
    def _severity_for_kind(finding_kind: str) -> Severity:
        """Map finding kind to advisory severity."""
        if finding_kind == "loop_diuretic_without_repletion":
            return Severity.HIGH
        return Severity.CRITICAL

    @staticmethod
    def _build_rationale(
        *,
        medication_name: str,
        agent: str,
        descriptor: str,
        finding_kind: str,
        potassium_mmol_l: float | None,
        magnesium_mg_dl: float | None,
        loop_diuretic_agents_found: list[str],
        repletion_agents_found: list[str],
    ) -> str:
        """Compose a RESEARCH USE ONLY digoxin toxicity rationale."""
        if finding_kind == "low_potassium":
            detail = (
                f"potassium is low at {potassium_mmol_l:.1f} mmol/L "
                f"(threshold < {_POTASSIUM_LOW_THRESHOLD_MMOL_L:.1f} mmol/L)"
            )
        elif finding_kind == "low_magnesium":
            detail = (
                f"magnesium is low at {magnesium_mg_dl:.2f} mg/dL "
                f"(threshold < {_MAGNESIUM_LOW_THRESHOLD_MG_DL:.1f} mg/dL)"
            )
        else:
            detail = (
                f"loop diuretic(s) ({', '.join(loop_diuretic_agents_found)}) are co-prescribed "
                "without documented potassium or magnesium repletion cues "
                "(potassium, kcl, magnesium, spironolactone, eplerenone, amiloride, triamterene)"
            )
            if repletion_agents_found:
                detail += f"; repletion agents present ({', '.join(repletion_agents_found)})"

        return (
            "RESEARCH USE ONLY: "
            f"Medication '{medication_name}' contains {agent}, {descriptor}. "
            f"Digoxin toxicity risk is elevated because {detail}. "
            "Hypokalemia, hypomagnesemia, and loop-diuretic-induced electrolyte loss "
            "increase digoxin binding and toxicity. Review electrolytes, repletion strategy, "
            "and digoxin level before continuing therapy."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
