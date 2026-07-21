"""STOPP/START older-adult prescribing-criteria safety checker.

STOPP (Screening Tool of Older Persons' Prescriptions) and START (Screening
Tool to Alert to Right Treatment) are complementary criteria for adults aged 65
and older: STOPP flags medications that should usually be stopped (or avoided),
while START flags therapies that should usually be started given a documented
indication. Unlike the AGS Beers Criteria checker — which is a single-agent PIM
list without indication-conditioned omissions — this hazard covers *both*
potentially inappropriate prescriptions *and* potentially omitted indicated
therapy, so it is not surfaced by Beers alone.

This checker applies only to patients aged 65 and older; below that age (or when
age is unknown) it returns no findings. For an eligible patient it matches
active medications and free-text conditions to a conservative, curated mini
rule set (whole-token matching, never loose substrings). It is deterministic
and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, StoppStartRisk

logger = get_logger(__name__)

# STOPP/START apply to older adults; aligned with the Beers age threshold.
_OLDER_ADULT_AGE_THRESHOLD: Final[int] = 65

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


class _StoppRule:
    """A curated STOPP (stop / avoid) panel entry.

    Attributes:
        criterion_id: Stable criterion identifier (e.g. ``STOPP-D1``).
        agents: Medication tokens that trigger the criterion when present.
        severity: Severity assigned when the rule fires.
        rationale: Short clinical reason for stopping/avoiding the agent.
        required_condition_aliases: When non-empty, at least one condition
            token must also match before the STOPP rule fires.
    """

    __slots__ = (
        "agents",
        "criterion_id",
        "rationale",
        "required_condition_aliases",
        "severity",
    )

    def __init__(
        self,
        criterion_id: str,
        agents: frozenset[str],
        severity: Severity,
        rationale: str,
        required_condition_aliases: frozenset[str] = frozenset(),
    ) -> None:
        """Initialize a STOPP panel entry."""
        self.criterion_id = criterion_id
        self.agents = agents
        self.severity = severity
        self.rationale = rationale
        self.required_condition_aliases = required_condition_aliases


class _StartRule:
    """A curated START (start / consider) panel entry.

    Attributes:
        criterion_id: Stable criterion identifier (e.g. ``START-A5``).
        expected_agents: Any one of these medication tokens satisfies the rule.
        condition_aliases: Condition tokens that establish the indication.
        severity: Severity assigned when the indication is present but therapy
            is absent.
        rationale: Short clinical reason for starting the therapy.
    """

    __slots__ = (
        "condition_aliases",
        "criterion_id",
        "expected_agents",
        "rationale",
        "severity",
    )

    def __init__(
        self,
        criterion_id: str,
        expected_agents: frozenset[str],
        condition_aliases: frozenset[str],
        severity: Severity,
        rationale: str,
    ) -> None:
        """Initialize a START panel entry."""
        self.criterion_id = criterion_id
        self.expected_agents = expected_agents
        self.condition_aliases = condition_aliases
        self.severity = severity
        self.rationale = rationale


# Conservative STOPP mini-set (RESEARCH USE ONLY approximations of common
# STOPP criteria). Agents and condition aliases are whole-token matched.
_STOPP_RULES: Final[tuple[_StoppRule, ...]] = (
    _StoppRule(
        "STOPP-D1",
        frozenset({"diazepam", "chlordiazepoxide", "flurazepam", "clonazepam"}),
        Severity.HIGH,
        "long-acting benzodiazepine in an older adult (falls, prolonged sedation)",
    ),
    _StoppRule(
        "STOPP-D2",
        frozenset({"amitriptyline", "imipramine", "doxepin"}),
        Severity.HIGH,
        "tertiary tricyclic antidepressant in an older adult (anticholinergic load)",
    ),
    _StoppRule(
        "STOPP-B1",
        frozenset({"digoxin"}),
        Severity.MODERATE,
        "digoxin in an older adult warrants dose/renal review (toxicity risk)",
    ),
    _StoppRule(
        "STOPP-H1",
        frozenset({"ibuprofen", "naproxen", "diclofenac", "indomethacin", "ketorolac"}),
        Severity.HIGH,
        "NSAID with heart failure (fluid retention / decompensation risk)",
        required_condition_aliases=frozenset(
            {"heart failure", "chf", "hfref", "hfpef", "cardiomyopathy"}
        ),
    ),
    _StoppRule(
        "STOPP-K1",
        frozenset({"glyburide", "glibenclamide", "chlorpropamide"}),
        Severity.HIGH,
        "long-acting sulfonylurea in an older adult (prolonged hypoglycaemia)",
    ),
)

# Conservative START mini-set: indication present + expected therapy absent.
_START_RULES: Final[tuple[_StartRule, ...]] = (
    _StartRule(
        "START-A5",
        frozenset(
            {
                "atorvastatin",
                "simvastatin",
                "rosuvastatin",
                "pravastatin",
                "lovastatin",
                "fluvastatin",
            }
        ),
        frozenset(
            {
                "myocardial infarction",
                "mi",
                "acs",
                "ascvd",
                "ischemic stroke",
                "ischaemic stroke",
                "stroke",
                "cad",
                "ihd",
            }
        ),
        Severity.HIGH,
        "statin indicated for secondary cardiovascular prevention",
    ),
    _StartRule(
        "START-A6",
        frozenset(
            {
                "lisinopril",
                "enalapril",
                "ramipril",
                "perindopril",
                "benazepril",
                "quinapril",
                "captopril",
                "fosinopril",
                "trandolapril",
                "losartan",
                "valsartan",
                "candesartan",
                "irbesartan",
                "olmesartan",
                "telmisartan",
            }
        ),
        frozenset({"heart failure", "chf", "hfref"}),
        Severity.HIGH,
        "ACE inhibitor or ARB indicated in symptomatic heart failure",
    ),
    _StartRule(
        "START-A1",
        frozenset(
            {
                "warfarin",
                "apixaban",
                "rivaroxaban",
                "dabigatran",
                "edoxaban",
            }
        ),
        frozenset({"atrial fibrillation", "afib", "a-fib"}),
        Severity.HIGH,
        "anticoagulant indicated for atrial fibrillation (stroke prevention)",
    ),
)


class StoppStartChecker:
    """Flag STOPP avoidances and START omissions for older adults."""

    def check(
        self,
        medications: list[Medication],
        age: int | None,
        conditions: list[str] | None = None,
    ) -> list[StoppStartRisk]:
        """Return STOPP/START findings for an older adult.

        The criteria apply only to adults aged 65 and older, so no finding is
        returned for a younger patient or when the age is unknown. STOPP rules
        fire when a listed agent is present (optionally requiring a matching
        condition). START rules fire when a matching indication is present but
        none of the expected agents appear in the medication list.

        Args:
            medications: Active patient medications.
            age: Patient age in years, or None when unknown.
            conditions: Free-text diagnoses / problem-list entries used for
                indication-conditioned STOPP and START rules.

        Returns:
            One :class:`StoppStartRisk` per fired criterion, ordered by
            descending severity then criterion id. An empty list is returned for
            patients under 65, unknown age, or when no criterion fires.
        """
        if age is None or age < _OLDER_ADULT_AGE_THRESHOLD:
            logger.info("stopp_start_checked", findings=0, eligible=False)
            return []

        med_tokens = self._medication_tokens(medications)
        condition_blob = self._condition_blob(conditions or [])
        findings: list[StoppStartRisk] = []

        for stopp_rule in _STOPP_RULES:
            if stopp_rule.required_condition_aliases and not self._aliases_match(
                condition_blob, stopp_rule.required_condition_aliases
            ):
                continue
            matched_agents = sorted(med_tokens.keys() & stopp_rule.agents)
            if not matched_agents:
                continue
            agent = matched_agents[0]
            medication_name = med_tokens[agent]
            findings.append(
                StoppStartRisk(
                    medication=medication_name,
                    agent=agent,
                    criterion_id=stopp_rule.criterion_id,
                    criterion_type="STOPP",
                    severity=stopp_rule.severity,
                    rationale=(
                        f"{stopp_rule.criterion_id}: medication '{medication_name}' contains "
                        f"{agent}; {stopp_rule.rationale} (patient age {age}). Consider "
                        f"stopping or switching to a safer alternative."
                    ),
                )
            )

        for start_rule in _START_RULES:
            if not self._aliases_match(condition_blob, start_rule.condition_aliases):
                continue
            if med_tokens.keys() & start_rule.expected_agents:
                continue
            expected = sorted(start_rule.expected_agents)[0]
            findings.append(
                StoppStartRisk(
                    medication=None,
                    agent=expected,
                    criterion_id=start_rule.criterion_id,
                    criterion_type="START",
                    severity=start_rule.severity,
                    rationale=(
                        f"{start_rule.criterion_id}: {start_rule.rationale} "
                        f"(patient age {age}); no matching therapy found among active "
                        f"medications. Consider starting an indicated agent "
                        f"(e.g. {expected}) if no contraindication."
                    ),
                )
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.criterion_id))
        logger.info("stopp_start_checked", findings=len(findings), eligible=True)
        return findings

    @staticmethod
    def _medication_tokens(medications: list[Medication]) -> dict[str, str]:
        """Map matched medication tokens to a representative display name.

        When the same token appears in multiple medication entries, the first
        medication name wins (deterministic iteration order).

        Args:
            medications: Active medications.

        Returns:
            Token → medication name mapping.
        """
        tokens: dict[str, str] = {}
        for medication in medications:
            for token in re.findall(r"[a-z0-9]+", medication.name.lower()):
                tokens.setdefault(token, medication.name)
        return tokens

    @staticmethod
    def _condition_blob(conditions: list[str]) -> str:
        """Join free-text conditions into a lowercase searchable blob.

        Args:
            conditions: Diagnosis / problem-list strings.

        Returns:
            Lowercased, space-joined condition text.
        """
        return " ".join(conditions).lower()

    @staticmethod
    def _aliases_match(blob: str, aliases: frozenset[str]) -> bool:
        """Return True when any alias matches as a whole token or phrase.

        Single-token aliases (e.g. ``chf``, ``ascvd``) must appear as whole
        alphanumeric tokens. Multi-word aliases (e.g. ``heart failure``) match
        as substrings of the condition blob so indication phrases stay tight.

        Args:
            blob: Lowercased condition text.
            aliases: Candidate indication aliases.

        Returns:
            Whether any alias is present.
        """
        if not blob or not aliases:
            return False
        tokens = set(re.findall(r"[a-z0-9]+", blob))
        for alias in aliases:
            alias_l = alias.lower()
            if " " in alias_l or "-" in alias_l:
                if alias_l in blob:
                    return True
                continue
            if alias_l in tokens:
                return True
        return False
