"""Antibiotic stewardship safety checker.

Antibiotic stewardship hazards are not limited to classic drug-drug
interactions or dose adjustment. Broad-spectrum agents without a documented
indication, duplicate antimicrobial coverage, and prolonged-course cues can
increase avoidable adverse effects, resistance pressure, and C. difficile risk.

This checker deterministically matches active medications to a conservative
antibiotic panel using whole-token matching (never loose substrings). It emits
advisory ``AntibioticStewardshipRisk`` records and is RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import AntibioticStewardshipRisk, Medication, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_PROLONGED_DURATION_THRESHOLD_DAYS: Final[float] = 14.0

_DURATION_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(
        r"\b(?:for|x|duration(?:\s+of)?|course(?:\s+of)?)\s*"
        r"(\d+(?:\.\d+)?)\s*(days?|d|weeks?|wks?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(\d+(?:\.\d+)?)\s*(days?|d|weeks?|wks?)\s*"
        r"(?:course|therapy|treatment)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bday\s*(\d+(?:\.\d+)?)\s*(?:of\s*)?"
        r"(?:therapy|treatment|antibiotics?)\b",
        re.IGNORECASE,
    ),
)
_PROLONGED_CUE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:chronic|long[-\s]?term|suppressive|indefinite|extended)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _AntibioticRule:
    """A canonical antibiotic entry in the stewardship panel."""

    agent: str
    aliases: frozenset[str]
    coverage_groups: frozenset[str]


@dataclass(frozen=True)
class _MatchedAntibiotic:
    """A medication entry matched to a canonical antibiotic agent."""

    medication_name: str
    agent: str
    coverage_groups: frozenset[str]
    duration_days: float | None
    has_prolonged_cue: bool


_ANTIBIOTIC_PANEL: Final[tuple[_AntibioticRule, ...]] = (
    _AntibioticRule(
        "ciprofloxacin",
        frozenset({"ciprofloxacin", "cipro"}),
        frozenset({"fluoroquinolone"}),
    ),
    _AntibioticRule(
        "levofloxacin",
        frozenset({"levofloxacin", "levo"}),
        frozenset({"fluoroquinolone"}),
    ),
    _AntibioticRule(
        "moxifloxacin",
        frozenset({"moxifloxacin"}),
        frozenset({"fluoroquinolone"}),
    ),
    _AntibioticRule("ofloxacin", frozenset({"ofloxacin"}), frozenset({"fluoroquinolone"})),
    _AntibioticRule("delafloxacin", frozenset({"delafloxacin"}), frozenset({"fluoroquinolone"})),
    _AntibioticRule(
        "azithromycin",
        frozenset({"azithromycin", "azithro"}),
        frozenset({"macrolide"}),
    ),
    _AntibioticRule("clarithromycin", frozenset({"clarithromycin"}), frozenset({"macrolide"})),
    _AntibioticRule("erythromycin", frozenset({"erythromycin"}), frozenset({"macrolide"})),
    _AntibioticRule(
        "metronidazole",
        frozenset({"metronidazole", "flagyl"}),
        frozenset({"anaerobic"}),
    ),
    _AntibioticRule("clindamycin", frozenset({"clindamycin"}), frozenset({"anaerobic"})),
    _AntibioticRule(
        "piperacillin",
        frozenset({"piperacillin", "zosyn"}),
        frozenset({"anaerobic", "antipseudomonal_beta_lactam"}),
    ),
    _AntibioticRule(
        "cefepime",
        frozenset({"cefepime"}),
        frozenset({"antipseudomonal_beta_lactam"}),
    ),
    _AntibioticRule(
        "ceftazidime",
        frozenset({"ceftazidime"}),
        frozenset({"antipseudomonal_beta_lactam"}),
    ),
    _AntibioticRule(
        "meropenem",
        frozenset({"meropenem"}),
        frozenset({"anaerobic", "antipseudomonal_beta_lactam"}),
    ),
    _AntibioticRule(
        "imipenem",
        frozenset({"imipenem"}),
        frozenset({"anaerobic", "antipseudomonal_beta_lactam"}),
    ),
    _AntibioticRule("ertapenem", frozenset({"ertapenem"}), frozenset({"anaerobic"})),
    _AntibioticRule("vancomycin", frozenset({"vancomycin", "vanco"}), frozenset({"mrsa"})),
    _AntibioticRule("linezolid", frozenset({"linezolid"}), frozenset({"mrsa"})),
    _AntibioticRule("daptomycin", frozenset({"daptomycin"}), frozenset({"mrsa"})),
    _AntibioticRule("ceftaroline", frozenset({"ceftaroline"}), frozenset({"mrsa"})),
    _AntibioticRule("tedizolid", frozenset({"tedizolid"}), frozenset({"mrsa"})),
    _AntibioticRule("amoxicillin", frozenset({"amoxicillin", "amox"}), frozenset()),
    _AntibioticRule("doxycycline", frozenset({"doxycycline", "doxy"}), frozenset()),
    _AntibioticRule("ceftriaxone", frozenset({"ceftriaxone"}), frozenset()),
    _AntibioticRule("nitrofurantoin", frozenset({"nitrofurantoin"}), frozenset()),
    _AntibioticRule(
        "trimethoprim-sulfamethoxazole",
        frozenset({"bactrim", "septra", "tmp", "smx"}),
        frozenset(),
    ),
)

_COVERAGE_LABELS: Final[dict[str, str]] = {
    "fluoroquinolone": "fluoroquinolone coverage",
    "macrolide": "macrolide coverage",
    "anaerobic": "anaerobic coverage",
    "antipseudomonal_beta_lactam": "antipseudomonal beta-lactam coverage",
    "mrsa": "MRSA coverage",
}

_FLUOROQUINOLONE_INDICATION_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "urinary tract infection",
        "uti",
        "pyelonephritis",
        "prostatitis",
        "pneumonia",
        "community acquired pneumonia",
        "cap",
        "hospital acquired pneumonia",
        "hap",
        "intra abdominal",
        "intra-abdominal",
        "diverticulitis",
        "pseudomonas",
        "febrile neutropenia",
        "anthrax",
        "infectious diarrhea",
        "traveler diarrhea",
        "travelers diarrhea",
        "traveler's diarrhea",
        "osteomyelitis",
        "complicated skin infection",
        "sepsis",
        "bacteremia",
    }
)


class AntibioticStewardshipChecker:
    """Flag advisory antibiotic-stewardship concerns."""

    def check(
        self,
        medications: list[Medication],
        indications: list[str] | None = None,
        clinical_notes: str | None = None,
    ) -> list[AntibioticStewardshipRisk]:
        """Return stewardship findings for active antibiotics.

        Args:
            medications: Active patient medications.
            indications: Free-text documented indications / diagnoses for
                antimicrobial therapy. Fluoroquinolones with no recognized
                indication in this context are flagged.
            clinical_notes: Optional free-text notes included in the indication
                context.

        Returns:
            Advisory stewardship findings ordered by descending severity then
            concern and medication/agent names. An empty list is returned when
            no panel antibiotic or stewardship concern is present.
        """
        matched_antibiotics = self._matched_antibiotics(medications)
        if not matched_antibiotics:
            logger.info("antibiotic_stewardship_checked", findings=0)
            return []

        indication_context = self._context_blob(indications or [], clinical_notes)
        findings: list[AntibioticStewardshipRisk] = []
        findings.extend(self._fluoroquinolone_findings(matched_antibiotics, indication_context))
        findings.extend(self._duplicate_coverage_findings(matched_antibiotics))
        findings.extend(self._prolonged_duration_findings(matched_antibiotics))

        findings.sort(
            key=lambda stewardship_finding: (
                -_SEVERITY_RANK[stewardship_finding.severity],
                stewardship_finding.concern,
                ",".join(stewardship_finding.medications).lower(),
                ",".join(stewardship_finding.agents).lower(),
            )
        )
        logger.info("antibiotic_stewardship_checked", findings=len(findings))
        return findings

    @classmethod
    def _fluoroquinolone_findings(
        cls,
        matched_antibiotics: list[_MatchedAntibiotic],
        indication_context: str,
    ) -> list[AntibioticStewardshipRisk]:
        """Return fluoroquinolone-without-indication findings."""
        if cls._aliases_match(indication_context, _FLUOROQUINOLONE_INDICATION_ALIASES):
            return []

        fluoroquinolone_findings: list[AntibioticStewardshipRisk] = []
        context_for_model = indication_context or None
        context_for_rationale = (
            indication_context if indication_context else "no documented indication"
        )
        for fluoroquinolone_match in matched_antibiotics:
            if "fluoroquinolone" not in fluoroquinolone_match.coverage_groups:
                continue
            fluoroquinolone_findings.append(
                AntibioticStewardshipRisk(
                    concern="fluoroquinolone_without_indication",
                    medications=[fluoroquinolone_match.medication_name],
                    agents=[fluoroquinolone_match.agent],
                    severity=Severity.HIGH,
                    indication_context=context_for_model,
                    rationale=(
                        f"Medication '{fluoroquinolone_match.medication_name}' contains "
                        f"{fluoroquinolone_match.agent}, a fluoroquinolone. The supplied "
                        f"indication context ({context_for_rationale}) does not document a "
                        f"recognized high-risk indication; review necessity, spectrum, and "
                        f"safer narrower alternatives."
                    ),
                )
            )
        return fluoroquinolone_findings

    @staticmethod
    def _duplicate_coverage_findings(
        matched_antibiotics: list[_MatchedAntibiotic],
    ) -> list[AntibioticStewardshipRisk]:
        """Return duplicate antimicrobial coverage findings."""
        group_to_matches: dict[str, list[_MatchedAntibiotic]] = {}
        for coverage_match in matched_antibiotics:
            for coverage_group in coverage_match.coverage_groups:
                group_to_matches.setdefault(coverage_group, []).append(coverage_match)

        duplicate_findings: list[AntibioticStewardshipRisk] = []
        for coverage_group_name, grouped_matches in group_to_matches.items():
            agent_to_medication: dict[str, str] = {}
            for grouped_antibiotic in grouped_matches:
                agent_to_medication.setdefault(
                    grouped_antibiotic.agent,
                    grouped_antibiotic.medication_name,
                )
            medication_names = sorted(set(agent_to_medication.values()))
            if len(agent_to_medication) < 2 or len(medication_names) < 2:
                continue
            agents = sorted(agent_to_medication)
            coverage_label = _COVERAGE_LABELS[coverage_group_name]
            duplicate_findings.append(
                AntibioticStewardshipRisk(
                    concern="duplicate_coverage",
                    medications=medication_names,
                    agents=agents,
                    severity=Severity.HIGH,
                    coverage_class=coverage_label,
                    rationale=(
                        f"Active antibiotics {', '.join(medication_names)} provide overlapping "
                        f"{coverage_label} via {', '.join(agents)}. Duplicate coverage can "
                        f"increase toxicity, C. difficile risk, and resistance pressure; review "
                        f"whether de-escalation or consolidation is appropriate."
                    ),
                )
            )
        return duplicate_findings

    @staticmethod
    def _prolonged_duration_findings(
        matched_antibiotics: list[_MatchedAntibiotic],
    ) -> list[AntibioticStewardshipRisk]:
        """Return prolonged antibiotic duration findings."""
        prolonged_findings: list[AntibioticStewardshipRisk] = []
        medication_names_seen: set[str] = set()
        for duration_match in matched_antibiotics:
            if duration_match.medication_name in medication_names_seen:
                continue
            medication_names_seen.add(duration_match.medication_name)
            has_duration_excess = (
                duration_match.duration_days is not None
                and duration_match.duration_days > _PROLONGED_DURATION_THRESHOLD_DAYS
            )
            if not has_duration_excess and not duration_match.has_prolonged_cue:
                continue
            if duration_match.duration_days is None:
                duration_phrase = "a chronic/extended duration cue"
            else:
                duration_phrase = f"a {duration_match.duration_days:g}-day duration cue"
            prolonged_findings.append(
                AntibioticStewardshipRisk(
                    concern="prolonged_duration",
                    medications=[duration_match.medication_name],
                    agents=[duration_match.agent],
                    severity=Severity.MODERATE,
                    duration_days=duration_match.duration_days,
                    rationale=(
                        f"Medication '{duration_match.medication_name}' contains "
                        f"{duration_match.agent} and includes {duration_phrase}. Antibiotic "
                        f"courses beyond {_PROLONGED_DURATION_THRESHOLD_DAYS:g} days or marked "
                        f"as chronic/extended warrant stewardship review for stop date, source "
                        f"control, culture results, and de-escalation."
                    ),
                )
            )
        return prolonged_findings

    @classmethod
    def _matched_antibiotics(cls, medications: list[Medication]) -> list[_MatchedAntibiotic]:
        """Match active medications to canonical antibiotic agents."""
        matched_antibiotics: list[_MatchedAntibiotic] = []
        for medication_entry in medications:
            medication_tokens = cls._tokens(medication_entry.name)
            if not medication_tokens:
                continue
            duration_days = cls._parse_duration_days(medication_entry)
            has_prolonged_cue = cls._has_prolonged_cue(medication_entry)
            matched_agents_for_medication: set[str] = set()
            for antibiotic_rule in _ANTIBIOTIC_PANEL:
                if not (medication_tokens & antibiotic_rule.aliases):
                    continue
                if antibiotic_rule.agent in matched_agents_for_medication:
                    continue
                matched_agents_for_medication.add(antibiotic_rule.agent)
                matched_antibiotics.append(
                    _MatchedAntibiotic(
                        medication_name=medication_entry.name,
                        agent=antibiotic_rule.agent,
                        coverage_groups=antibiotic_rule.coverage_groups,
                        duration_days=duration_days,
                        has_prolonged_cue=has_prolonged_cue,
                    )
                )
        return matched_antibiotics

    @classmethod
    def _parse_duration_days(cls, medication: Medication) -> float | None:
        """Parse an antibiotic-course duration in days from medication text."""
        text = cls._medication_blob(medication)
        durations: list[float] = []
        for duration_pattern in _DURATION_PATTERNS:
            for duration_match in duration_pattern.finditer(text):
                magnitude = float(duration_match.group(1))
                unit = duration_match.group(2).lower()
                if unit.startswith("w"):
                    durations.append(magnitude * 7.0)
                else:
                    durations.append(magnitude)
        if not durations:
            return None
        return max(durations)

    @classmethod
    def _has_prolonged_cue(cls, medication: Medication) -> bool:
        """Return True when medication text contains chronic/extended course cues."""
        return bool(_PROLONGED_CUE_PATTERN.search(cls._medication_blob(medication)))

    @staticmethod
    def _medication_blob(medication: Medication) -> str:
        """Join medication free-text fields into one searchable string."""
        return " ".join(
            medication_part
            for medication_part in (
                medication.name,
                medication.dosage,
                medication.route,
                medication.frequency,
            )
            if medication_part
        )

    @staticmethod
    def _context_blob(indications: list[str], clinical_notes: str | None) -> str:
        """Join indication strings and optional clinical notes into normalized text."""
        context_parts = [indication for indication in indications if indication.strip()]
        if clinical_notes and clinical_notes.strip():
            context_parts.append(clinical_notes)
        return " ".join(context_parts).strip().lower()

    @classmethod
    def _aliases_match(cls, blob: str, aliases: frozenset[str]) -> bool:
        """Return True when any alias matches as a whole token or phrase."""
        if not blob or not aliases:
            return False
        normalized_blob = cls._normalise_text(blob)
        blob_tokens = set(normalized_blob.split())
        padded_blob = f" {normalized_blob} "
        for indication_alias in aliases:
            normalized_alias = cls._normalise_text(indication_alias)
            if " " in normalized_alias:
                if f" {normalized_alias} " in padded_blob:
                    return True
                continue
            if normalized_alias in blob_tokens:
                return True
        return False

    @staticmethod
    def _normalise_text(text: str) -> str:
        """Normalize text to lowercase alphanumeric tokens separated by spaces."""
        return " ".join(re.findall(r"[a-z0-9]+", text.lower()))

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
