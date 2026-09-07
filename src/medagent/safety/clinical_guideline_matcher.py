"""Clinical guideline matcher — educational condition → guideline cues.

The existing
:class:`~medagent.safety.disease_contraindication_checker.DiseaseContraindicationChecker`
flags curated **condition × drug contraindication** panels (for example heart
failure + NSAIDs). It does **not** surface positive educational guideline
reminders such as HFrEF GDMT building blocks or hypertension first-line classes.

This matcher fills that gap with a small educational guideline panel. It matches
patient conditions (whole-token) and optionally notes which guideline cue agents
are already present on the medication list. Findings are advisory RESEARCH USE
ONLY records and never modify medications or prescribe therapy.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import GuidelineMatch, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_CONDITION_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "hfref": (
        "hfref",
        "heart failure with reduced ejection fraction",
        "systolic heart failure",
        "reduced ejection fraction heart failure",
    ),
    "heart_failure": (
        "heart failure",
        "congestive heart failure",
        "chf",
        "cardiac failure",
    ),
    "hypertension": (
        "hypertension",
        "essential hypertension",
        "high blood pressure",
        "htn",
    ),
    "type2_diabetes": (
        "type 2 diabetes",
        "type2 diabetes",
        "t2dm",
        "niddm",
        "diabetes mellitus type 2",
    ),
    "ckd": (
        "ckd",
        "chronic kidney disease",
        "chronic renal failure",
    ),
    "atrial_fibrillation": (
        "atrial fibrillation",
        "afib",
        "a fib",
        "nonvalvular atrial fibrillation",
    ),
    "secondary_prevention_ascvd": (
        "ascvd",
        "coronary artery disease",
        "cad",
        "prior mi",
        "myocardial infarction",
        "ischemic stroke",
    ),
}

# guideline_id -> (condition_key, cue_agents, severity, guideline_label, educational_cue)
_GUIDELINES: Final[dict[str, tuple[str, frozenset[str], Severity, str, str]]] = {
    "hf_gdmt": (
        "hfref",
        frozenset(
            {
                "sacubitril",
                "valsartan",
                "enalapril",
                "lisinopril",
                "ramipril",
                "carvedilol",
                "metoprolol",
                "bisoprolol",
                "dapagliflozin",
                "empagliflozin",
                "spironolactone",
                "eplerenone",
            }
        ),
        Severity.MODERATE,
        "HFrEF GDMT building blocks (educational)",
        "Review foundational HFrEF GDMT classes (ARNI/ACEi/ARB, evidence-based "
        "beta-blocker, MRA, SGLT2 inhibitor) when clinically appropriate",
    ),
    "hf_general_gdmt_cue": (
        "heart_failure",
        frozenset(
            {
                "sacubitril",
                "enalapril",
                "lisinopril",
                "carvedilol",
                "metoprolol",
                "dapagliflozin",
                "empagliflozin",
                "spironolactone",
            }
        ),
        Severity.LOW,
        "Heart-failure GDMT awareness (educational)",
        "Consider whether guideline-directed medical therapy elements are documented",
    ),
    "htn_first_line": (
        "hypertension",
        frozenset(
            {
                "lisinopril",
                "enalapril",
                "ramipril",
                "losartan",
                "valsartan",
                "amlodipine",
                "chlorthalidone",
                "hydrochlorothiazide",
                "hctz",
                "indapamide",
            }
        ),
        Severity.LOW,
        "Hypertension first-line classes (educational)",
        "First-line educational classes include thiazide-like diuretic, CCB, "
        "ACEi, or ARB per typical adult HTN guidance",
    ),
    "t2dm_cardiorenal": (
        "type2_diabetes",
        frozenset(
            {
                "metformin",
                "dapagliflozin",
                "empagliflozin",
                "canagliflozin",
                "semaglutide",
                "liraglutide",
                "dulaglutide",
            }
        ),
        Severity.LOW,
        "T2DM cardiorenal-protective therapy cues (educational)",
        "Educational review of metformin foundation and SGLT2i/GLP-1 RA when "
        "cardiorenal indications apply",
    ),
    "ckd_acei_sglt2": (
        "ckd",
        frozenset(
            {
                "lisinopril",
                "enalapril",
                "ramipril",
                "losartan",
                "dapagliflozin",
                "empagliflozin",
                "canagliflozin",
            }
        ),
        Severity.MODERATE,
        "CKD ACEi/ARB + SGLT2 educational cues",
        "Educational CKD guidance often emphasizes ACEi/ARB and SGLT2 inhibitors "
        "when indicated and tolerated",
    ),
    "afib_stroke_prevention": (
        "atrial_fibrillation",
        frozenset(
            {
                "apixaban",
                "rivaroxaban",
                "edoxaban",
                "dabigatran",
                "warfarin",
            }
        ),
        Severity.MODERATE,
        "Atrial fibrillation stroke-prevention cue (educational)",
        "Educational reminder to assess stroke-prevention anticoagulation when "
        "clinically appropriate (not a CHA2DS2-VASc calculator)",
    ),
    "ascvd_secondary_prevention": (
        "secondary_prevention_ascvd",
        frozenset(
            {
                "atorvastatin",
                "rosuvastatin",
                "aspirin",
                "clopidogrel",
                "ticagrelor",
            }
        ),
        Severity.LOW,
        "ASCVD secondary-prevention cue (educational)",
        "Educational secondary-prevention cues include high-intensity statin and "
        "antiplatelet therapy when indicated",
    ),
}


class ClinicalGuidelineMatcher:
    """Match conditions to a curated educational clinical-guideline panel."""

    def check(
        self,
        conditions: list[str],
        medications: list[Medication] | None = None,
    ) -> list[GuidelineMatch]:
        """Return advisory guideline matches for recognized conditions.

        Args:
            conditions: Patient condition/diagnosis strings.
            medications: Optional active medications used only to annotate which
                educational cue agents are already present. Absence of cue
                agents does **not** block a guideline match.

        Returns:
            One :class:`GuidelineMatch` per unique (guideline_id, condition)
            hit, ordered by descending severity then guideline id. Distinct from
            :class:`DiseaseContraindicationChecker` condition×drug
            contraindication panels.
        """
        medications = medications or []
        med_tokens: set[str] = set()
        for medication in medications:
            med_tokens |= self._tokens(medication.name)

        matched_conditions: list[tuple[str, str]] = []
        for condition in conditions:
            for condition_key in _CONDITION_ALIASES:
                if self._condition_match(condition, condition_key):
                    matched_conditions.append((condition, condition_key))

        if not matched_conditions:
            logger.info("clinical_guideline_matched", findings=0)
            return []

        findings: list[GuidelineMatch] = []
        seen: set[tuple[str, str]] = set()

        for condition, condition_key in matched_conditions:
            for guideline_id, (
                panel_condition,
                cue_agents,
                severity,
                guideline_label,
                educational_cue,
            ) in _GUIDELINES.items():
                if panel_condition != condition_key:
                    continue
                key = (guideline_id, condition)
                if key in seen:
                    continue
                seen.add(key)
                present = sorted(med_tokens & cue_agents)
                findings.append(
                    GuidelineMatch(
                        condition=condition,
                        condition_key=condition_key,
                        guideline_id=guideline_id,
                        guideline_label=guideline_label,
                        educational_cue=educational_cue,
                        present_cue_agents=present,
                        severity=severity,
                        rationale=(
                            "RESEARCH USE ONLY: Condition "
                            f"'{condition}' matched educational guideline panel "
                            f"'{guideline_id}' ({guideline_label}). Cue: "
                            f"{educational_cue}. Present cue agents on the "
                            f"medication list: {present or 'none documented'}. "
                            "This is a positive guideline-awareness screen, "
                            "distinct from DiseaseContraindicationChecker "
                            "condition×drug contraindication panels, and not a "
                            "treatment order. Confirm with a qualified clinician; "
                            "prefer frontier summarization with GPT-5.5 / "
                            "Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                        ),
                    )
                )

        findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK[finding.severity],
                finding.guideline_id,
                finding.condition.lower(),
            )
        )
        logger.info("clinical_guideline_matched", findings=len(findings))
        return findings

    def _condition_match(self, condition: str, condition_key: str) -> bool:
        """Return True when condition text whole-token-matches a panel alias."""
        ordered = self._ordered_tokens(condition)
        if not ordered:
            return False
        token_set = set(ordered)
        for alias in _CONDITION_ALIASES[condition_key]:
            alias_tokens = self._ordered_tokens(alias)
            if not alias_tokens:
                continue
            if len(alias_tokens) == 1:
                if alias_tokens[0] in token_set:
                    return True
                continue
            n = len(alias_tokens)
            for index in range(len(ordered) - n + 1):
                if ordered[index : index + n] == alias_tokens:
                    return True
        return False

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))

    @staticmethod
    def _ordered_tokens(name: str) -> list[str]:
        """Return lowercase alphanumeric tokens in order."""
        return re.findall(r"[a-z0-9]+", name.lower())
