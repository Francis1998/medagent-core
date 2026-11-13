"""Deterministic criterion evaluation, trial status and ranking for trial pre-screening.

Each criterion becomes ``met``, ``not_met``, ``insufficient_data`` or
``requires_human_review`` with evidence pointers. Absence counts as evidence
only when the record documents the domain (at least one Condition or medication
was supplied); otherwise the criterion is ``insufficient_data``. A lab criterion
is decided by the most recent matching Observation in its window, and is
``insufficient_data`` when that result cannot be compared. Free-text criteria
are never interpreted.

Trial status, with exclusion precedence:

* ``likely_ineligible`` — an exclusion criterion is met or an inclusion
  criterion is not met (blocking criteria list exclusions first);
* ``needs_review`` — nothing blocks, but a criterion is ``insufficient_data``
  or ``requires_human_review``;
* ``potentially_eligible`` — every criterion was decided favourably.

Ranking sorts by status, then fewer blocking criteria, a higher share of
favourable criteria, fewer open criteria, and finally the trial id, so equal
inputs always give equal output. RESEARCH USE ONLY.
"""

from __future__ import annotations

import bisect
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Any

from medagent.trials.criteria import Criterion, TrialDefinition, shift_by_age
from medagent.trials.facts import (
    Coding,
    Concept,
    ConceptIndex,
    ConditionFact,
    ObservationFact,
    PatientFacts,
    StatusFact,
)
from medagent.trials.schema import (
    EXCLUSION,
    INCLUSION,
    INSUFFICIENT_DATA,
    LIKELY_INELIGIBLE,
    MEDICATION_CLASSES,
    MET,
    NEEDS_REVIEW,
    NOT_MET,
    POTENTIALLY_ELIGIBLE,
    REQUIRES_HUMAN_REVIEW,
    TRIAL_STATUSES,
)
from medagent.trials.units import convert

MAX_EVIDENCE = 5
_STATUS_RANK = {status: rank for rank, status in enumerate(TRIAL_STATUSES)}
_SYSTEM_LABELS = {
    "http://snomed.info/sct": "SNOMED CT",
    "http://loinc.org": "LOINC",
    "http://hl7.org/fhir/sid/icd-10-cm": "ICD-10-CM",
    "http://hl7.org/fhir/sid/icd-10": "ICD-10",
    "http://www.nlm.nih.gov/research/umls/rxnorm": "RxNorm",
}
_RXNORM_SYSTEM = "http://www.nlm.nih.gov/research/umls/rxnorm"
_UNCERTAIN_VERIFICATION = frozenset({"unconfirmed", "provisional", "differential"})
_ACTIVE = frozenset({"active", "recurrence", "relapse"})
_INACTIVE = frozenset({"inactive", "remission", "resolved"})
_DISPLAY_QUANTUM = Decimal("0.0001")
_WITHHELD = "date withheld: a possible birth date"


@dataclass(frozen=True)
class Evidence:
    """A pointer to the de-identified fact behind a decision (never an identifier)."""

    resource_type: str
    system: str | None = None
    code: str | None = None
    display: str | None = None
    value: Decimal | bool | str | None = None
    comparator: str | None = None
    unit: str | None = None
    recorded: date | None = None

    def as_dict(self) -> dict[str, Any]:
        """JSON-ready evidence pointer."""
        value: Any = self.value
        if isinstance(value, Decimal):
            value = int(value) if value == value.to_integral_value() else float(value)
        return {
            "resource_type": self.resource_type,
            "system": self.system,
            "code": self.code,
            "display": self.display,
            "value": value,
            "comparator": self.comparator,
            "unit": self.unit,
            "date": self.recorded.isoformat() if self.recorded is not None else None,
        }


@dataclass(frozen=True)
class CriterionResult:
    """The decision for one criterion."""

    criterion: Criterion
    status: str
    rationale: str
    evidence: tuple[Evidence, ...] = ()

    @property
    def favourable(self) -> bool:
        """An inclusion criterion that is met, or an exclusion criterion that is not."""
        wanted = MET if self.criterion.section == INCLUSION else NOT_MET
        return self.status == wanted

    @property
    def blocking(self) -> bool:
        """An inclusion criterion that is not met, or an exclusion criterion that is."""
        unwanted = NOT_MET if self.criterion.section == INCLUSION else MET
        return self.status == unwanted

    @property
    def open(self) -> bool:
        """Undecided: missing data or a criterion only a human can judge."""
        return self.status in {INSUFFICIENT_DATA, REQUIRES_HUMAN_REVIEW}

    def as_dict(self) -> dict[str, Any]:
        """JSON-ready criterion result."""
        criterion = self.criterion
        return {
            "criterion_id": criterion.id,
            "section": criterion.section,
            "type": criterion.type,
            "text": criterion.text,
            "status": self.status,
            "rationale": self.rationale,
            "evidence": [item.as_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class TrialResult:
    """Every criterion decision for one trial and the resulting status."""

    trial: TrialDefinition
    results: tuple[CriterionResult, ...]
    status: str
    blocking: tuple[CriterionResult, ...]
    open: tuple[CriterionResult, ...]

    @property
    def favourable(self) -> int:
        """Number of criteria decided favourably."""
        return sum(result.favourable for result in self.results)

    @property
    def score(self) -> Fraction:
        """Share of all criteria decided favourably (0..1)."""
        return Fraction(self.favourable, len(self.results)) if self.results else Fraction(0)


@dataclass(frozen=True)
class RankedTrial:
    """A trial result with its 1-based rank and the explanation of its position."""

    rank: int
    result: TrialResult
    reason: str

    def as_dict(self) -> dict[str, Any]:
        """JSON-ready trial result."""
        result = self.result
        counts = Counter(item.status for item in result.results)
        return {
            "rank": self.rank,
            "trial_id": result.trial.trial_id,
            "trial_version": result.trial.version,
            "title": result.trial.title,
            "status": result.status,
            "score": round(float(result.score), 3),
            "rank_reason": self.reason,
            "counts": {
                MET: counts[MET],
                NOT_MET: counts[NOT_MET],
                INSUFFICIENT_DATA: counts[INSUFFICIENT_DATA],
                REQUIRES_HUMAN_REVIEW: counts[REQUIRES_HUMAN_REVIEW],
                "favourable": result.favourable,
                "blocking": len(result.blocking),
                "open": len(result.open),
                "total": len(result.results),
            },
            "blocking_criteria": [item.criterion.id for item in result.blocking],
            "open_criteria": [item.criterion.id for item in result.open],
            "eligibility_module": dict(result.trial.eligibility),
            "criteria": [item.as_dict() for item in result.results],
        }


@dataclass(frozen=True)
class _Outcome:
    """Whether a criterion's statement holds (None: undecided) and why."""

    holds: bool | None
    rationale: str
    evidence: tuple[Evidence, ...] = ()
    review: bool = False


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _fmt(value: Decimal) -> str:
    """Plain decimal text, at most four decimal places."""
    try:
        exponent = value.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -4:
            value = value.quantize(_DISPLAY_QUANTUM)
        text = format(value.normalize(), "f")
    except InvalidOperation:
        text = str(value)
    return text


def _system_label(system: str | None) -> str:
    if not system:
        return "uncoded"
    return _SYSTEM_LABELS.get(system.strip().rstrip("/").lower(), system)


def _coded(codings: Sequence[Coding]) -> Coding | None:
    return next((coding for coding in codings if coding.system and coding.code), None)


def _threshold(criterion: Criterion) -> str:
    unit = "x ULN" if criterion.relative_to == "uln" else (criterion.unit or "")
    if criterion.operator == "between" and criterion.low is not None and criterion.high is not None:
        return f"between {_fmt(criterion.low)} and {_fmt(criterion.high)} {unit}".rstrip()
    assert criterion.value is not None
    return f"{criterion.operator} {_fmt(criterion.value)} {unit}".rstrip()


def _days_before(facts: PatientFacts, recorded: date) -> int:
    return (facts.as_of - recorded).days


def _when(facts: PatientFacts, recorded: date | None) -> str:
    """A date for a rationale, withheld when it could reveal the date of birth."""
    if recorded is None:
        return "undated"
    if facts.exportable(recorded) is None:
        return _WITHHELD
    return f"{recorded.isoformat()}, {_days_before(facts, recorded)} days before as_of"


# ---------------------------------------------------------------------------
# Concept matching
# ---------------------------------------------------------------------------


def _contains_phrase(words: tuple[str, ...], phrase: tuple[str, ...]) -> bool:
    size = len(phrase)
    return any(words[index : index + size] == phrase for index in range(len(words) - size + 1))


def _concept_match(concept: Concept, criterion: Criterion) -> tuple[str, Coding | None] | None:
    """Return ('code' | 'term', the coding to cite) when the recorded concept matches."""
    for reference in criterion.codes:
        for coding in concept.codings:
            key = coding.key
            if key is None or key[0] != reference.system:
                continue
            if key[1] == reference.code or (reference.prefix and key[1].startswith(reference.code)):
                return "code", coding
    for phrase in criterion.terms:
        if any(_contains_phrase(words, phrase) for words in concept.words):
            return "term", _coded(concept.codings)
    return None


def _candidates(index: ConceptIndex, criterion: Criterion) -> list[int]:
    """Positions of facts that may match: shared codes, code prefixes or a term's first word."""
    found: set[int] = set()
    for reference in criterion.codes:
        if not reference.prefix:
            found.update(index.by_key.get((reference.system, reference.code), ()))
            continue
        codes = index.codes_by_system.get(reference.system, ())
        start = bisect.bisect_left(codes, reference.code)
        for code in codes[start:]:
            if not code.startswith(reference.code):
                break
            found.update(index.by_key[(reference.system, code)])
    for phrase in criterion.terms:
        found.update(index.by_word.get(phrase[0], ()))
    return sorted(found)


def _matching(
    concepts: Sequence[Concept], index: ConceptIndex, criterion: Criterion
) -> list[tuple[int, Coding | None, str]]:
    """(position, coding to cite, 'code' | 'term') for every fact that matches."""
    matches: list[tuple[int, Coding | None, str]] = []
    for position in _candidates(index, criterion):
        match = _concept_match(concepts[position], criterion)
        if match is not None:
            matches.append((position, match[1], match[0]))
    return matches


# ---------------------------------------------------------------------------
# Criterion evaluators
# ---------------------------------------------------------------------------


def _apply_presence(criterion: Criterion, found: bool | None) -> bool | None:
    if found is None or criterion.presence == "present":
        return found
    return not found


def _condition_evidence(
    fact: ConditionFact, coding: Coding | None, facts: PatientFacts
) -> Evidence:
    cited = coding or _coded(fact.concept.codings)
    return Evidence(
        resource_type="Condition",
        system=cited.system if cited else None,
        code=cited.code if cited else None,
        display=fact.concept.displays[0] if fact.concept.displays else None,
        value=fact.clinical_status,
        recorded=facts.exportable(fact.onset),
    )


def _condition_qualifies(fact: ConditionFact, criterion: Criterion, facts: PatientFacts) -> str:
    """'yes', or why a matching Condition does not count ('no: ...' / 'unknown: ...')."""
    status = fact.clinical_status
    if criterion.condition_status == "active":
        if status in _INACTIVE:
            return f"no: clinicalStatus {status}"
        if status not in _ACTIVE:
            return "unknown: clinicalStatus missing or unrecognised"
    if criterion.within_days is not None:
        if fact.onset is None:
            return "unknown: no onset date"
        days = _days_before(facts, fact.onset)
        if days < 0:
            return "unknown: onset after as_of"
        if days > criterion.within_days:
            return f"no: onset before the {criterion.within_days}-day window"
    if fact.verification_status in _UNCERTAIN_VERIFICATION:
        return f"unknown: verificationStatus {fact.verification_status}"
    return "yes"


def _evaluate_condition(criterion: Criterion, facts: PatientFacts) -> _Outcome:
    qualifying: list[tuple[ConditionFact, str, Coding | None]] = []
    undecided: list[tuple[ConditionFact, str, Coding | None]] = []
    rejected: list[tuple[ConditionFact, str, Coding | None]] = []
    concepts = [fact.concept for fact in facts.conditions]
    for position, coding, how in _matching(concepts, facts.condition_index, criterion):
        fact = facts.conditions[position]
        verdict = _condition_qualifies(fact, criterion, facts)
        if verdict == "yes":
            qualifying.append((fact, how, coding))
        elif verdict.startswith("unknown"):
            undecided.append((fact, verdict, coding))
        else:
            rejected.append((fact, verdict, coding))
    supplied = facts.condition_resources
    window = f" within {criterion.within_days} days" if criterion.within_days else ""
    scope = "active " if criterion.condition_status == "active" else ""
    found: bool | None
    if qualifying:
        fact, how, coding = qualifying[0]
        names = fact.concept.displays
        name = names[0] if names else "an uncoded condition"
        cited = coding or _coded(fact.concept.codings)
        code = f" ({_system_label(cited.system)} {cited.code})" if cited else ""
        found = True
        rationale = f"Found {scope}Condition '{name}'{code}{window}, matched by {how}."
        listed = qualifying
    elif undecided:
        found = None
        reasons = "; ".join(
            sorted({verdict.removeprefix("unknown: ") for _, verdict, _ in undecided})
        )
        rationale = f"A matching Condition could not be confirmed ({reasons})."
        listed = undecided
    elif supplied:
        found = False
        detail = ""
        if rejected:
            reasons = "; ".join(
                sorted({verdict.removeprefix("no: ") for _, verdict, _ in rejected})
            )
            detail = f" ({len(rejected)} match(es) did not qualify: {reasons})"
        rationale = (
            f"No {scope}matching Condition{window} among {supplied} supplied Condition "
            f"resource(s){detail}; absence from a partial record is not proof of absence."
        )
        listed = rejected
    else:
        found = None
        rationale = "No Condition resources were supplied."
        listed = []
    evidence = tuple(
        _condition_evidence(fact, coding, facts) for fact, _, coding in listed[:MAX_EVIDENCE]
    )
    return _Outcome(_apply_presence(criterion, found), rationale, evidence)


def _medication_match(
    tokens: frozenset[str], rxnorm: str | None, criterion: Criterion
) -> str | None:
    for label, ingredient in criterion.ingredients:
        if ingredient <= tokens:
            return f"ingredient '{label}'"
    for class_name in criterion.classes:
        if tokens & MEDICATION_CLASSES[class_name]:
            return f"class {class_name}"
    if rxnorm is not None and rxnorm in criterion.rxnorm_codes:
        return "RxNorm code"
    return None


def _evaluate_medication(criterion: Criterion, facts: PatientFacts) -> _Outcome:
    matches = [
        (medication, how)
        for medication in facts.medications
        if (how := _medication_match(medication.tokens, medication.rxnorm_key, criterion))
    ]
    evidence = tuple(
        Evidence(
            resource_type=medication.resource_type,
            system=_RXNORM_SYSTEM if medication.rxnorm_code else None,
            code=medication.rxnorm_code,
            display=medication.name,
            value="current",
            recorded=facts.exportable(medication.recorded),
        )
        for medication, _ in matches[:MAX_EVIDENCE]
    )
    found: bool | None
    if matches:
        medication, how = matches[0]
        found = True
        rationale = f"Current medication '{medication.name}' matches by {how}."
    elif facts.unnamed_current_medications:
        found = None
        rationale = (
            f"No named current medication matches, but {facts.unnamed_current_medications} "
            "current medication(s) could not be named, so absence cannot be confirmed."
        )
    elif facts.medication_resources:
        found = False
        rationale = (
            f"No current (active or on-hold) medication matches among "
            f"{facts.medication_resources} supplied medication resource(s); absence from a "
            "partial record is not proof of absence."
        )
    else:
        found = None
        rationale = "No MedicationRequest or MedicationStatement resources were supplied."
    return _Outcome(_apply_presence(criterion, found), rationale, evidence)


@dataclass(frozen=True)
class _Interval:
    """The set of values an observation allows (comparators make it open-ended)."""

    low: Decimal | None
    low_closed: bool
    high: Decimal | None
    high_closed: bool

    @classmethod
    def of(cls, value: Decimal, comparator: str | None) -> _Interval:
        if comparator == "<":
            return cls(None, False, value, False)
        if comparator == "<=":
            return cls(None, False, value, True)
        if comparator == ">":
            return cls(value, False, None, False)
        if comparator == ">=":
            return cls(value, True, None, False)
        return cls(value, True, value, True)

    def scaled(self, convert_value: Callable[[Decimal], Decimal | None]) -> _Interval | None:
        """Apply a positive, monotonic conversion to both ends."""
        low = convert_value(self.low) if self.low is not None else None
        high = convert_value(self.high) if self.high is not None else None
        if (self.low is not None and low is None) or (self.high is not None and high is None):
            return None
        return _Interval(low, self.low_closed, high, self.high_closed)

    def describe(self, unit: str) -> str:
        if self.low is not None and self.high is not None and self.low == self.high:
            return f"{_fmt(self.low)} {unit}".rstrip()
        if self.high is not None:
            return f"{'<=' if self.high_closed else '<'}{_fmt(self.high)} {unit}".rstrip()
        assert self.low is not None
        return f"{'>=' if self.low_closed else '>'}{_fmt(self.low)} {unit}".rstrip()


def _above(interval: _Interval, threshold: Decimal, inclusive: bool) -> bool | None:
    """Whether every allowed value is >= (or >) the threshold; None when it depends."""
    low, high = interval.low, interval.high
    if inclusive:
        if low is not None and low >= threshold:
            return True
        if high is not None and (
            high < threshold or (high == threshold and not interval.high_closed)
        ):
            return False
        return None
    if low is not None and (low > threshold or (low == threshold and not interval.low_closed)):
        return True
    if high is not None and high <= threshold:
        return False
    return None


def _decide(interval: _Interval, criterion: Criterion) -> bool | None:
    """Whether the observed interval satisfies the criterion's comparison."""
    operator = criterion.operator
    if operator == "between":
        assert criterion.low is not None and criterion.high is not None
        above_low = _above(interval, criterion.low, inclusive=True)
        above_high = _above(interval, criterion.high, inclusive=False)
        if above_low is False or above_high is True:
            return False
        if above_low is True and above_high is False:
            return True
        return None
    assert criterion.value is not None
    if operator in {">=", ">"}:
        return _above(interval, criterion.value, inclusive=operator == ">=")
    above = _above(interval, criterion.value, inclusive=operator == "<")
    return None if above is None else not above


def _upper_limit(fact: ObservationFact) -> Decimal | None:
    """The reference-range upper limit in the observation's own unit, if usable."""
    limit = fact.reference_high
    source, target = fact.reference_high_unit, fact.unit
    if limit is not None and source and target and source.strip().lower() != target.strip().lower():
        limit = convert(limit, source, target)
    return limit if limit is not None and limit > 0 else None


def _observed(fact: ObservationFact, criterion: Criterion) -> tuple[_Interval | None, str]:
    """The observation in criterion units (or x ULN), or why it cannot be compared."""
    if fact.value is None:
        return None, "no numeric value"
    interval = _Interval.of(fact.value, fact.comparator)
    if criterion.relative_to == "uln":
        uln = _upper_limit(fact)
        if uln is None:
            return None, "no usable reference-range upper limit"
        return interval.scaled(lambda value: value / uln), "x ULN"
    assert criterion.unit is not None
    unit = criterion.unit
    scaled = interval.scaled(lambda value: convert(value, fact.unit, unit))
    if scaled is None:
        return None, "missing or incompatible unit"
    return scaled, unit


def _describe_observed(fact: ObservationFact, interval: _Interval, unit: str) -> str:
    """The recorded value, plus its converted form when conversion changed the numbers."""
    assert fact.value is not None
    label = fact.unit_label or ""
    original = _Interval.of(fact.value, fact.comparator)
    recorded = original.describe(label)
    if unit == "x ULN":
        uln = _upper_limit(fact)
        assert uln is not None
        return f"{recorded} with upper limit {_fmt(uln)} {label}".rstrip() + (
            f" = {interval.describe(unit)}"
        )
    if (original.low, original.high) == (interval.low, interval.high):
        return recorded if label else interval.describe(unit)
    return f"{recorded} (= {interval.describe(unit)})"


def _observation_evidence(
    fact: ObservationFact, coding: Coding | None, facts: PatientFacts
) -> Evidence:
    cited = coding or _coded(fact.concept.codings)
    return Evidence(
        resource_type="Observation",
        system=cited.system if cited else None,
        code=cited.code if cited else None,
        display=fact.concept.displays[0] if fact.concept.displays else None,
        value=fact.value,
        comparator=fact.comparator,
        unit=fact.unit_label,
        recorded=facts.exportable(fact.effective),
    )


def _reasons(counts: Counter[str]) -> str:
    return "; ".join(f"{count} {reason}" for reason, count in sorted(counts.items()))


def _evaluate_lab(criterion: Criterion, facts: PatientFacts) -> _Outcome:
    concepts = [fact.concept for fact in facts.observations]
    matches = [
        (facts.observations[position], coding)
        for position, coding, _ in _matching(concepts, facts.observation_index, criterion)
    ]
    if not matches:
        return _Outcome(
            None,
            f"No matching Observation among {facts.observation_resources} supplied Observation "
            "resource(s).",
        )
    in_scope: list[tuple[ObservationFact, Coding | None]] = []
    skipped: Counter[str] = Counter()
    window = criterion.within_days
    for fact, coding in matches:
        if fact.effective is not None and fact.effective > facts.as_of:
            skipped["dated after as_of"] += 1
        elif window is not None and fact.effective is None:
            skipped["undated"] += 1
        elif window is not None and fact.effective and _days_before(facts, fact.effective) > window:
            skipped[f"older than {window} days"] += 1
        else:
            in_scope.append((fact, coding))
    if not in_scope:
        evidence = tuple(
            _observation_evidence(fact, coding, facts) for fact, coding in matches[:MAX_EVIDENCE]
        )
        return _Outcome(None, f"No usable matching Observation ({_reasons(skipped)}).", evidence)
    dates: list[date] = [fact.effective for fact, _ in in_scope if fact.effective is not None]
    latest = max(dates, default=None)
    current = [(fact, coding) for fact, coding in in_scope if fact.effective == latest]
    when = _when(facts, latest)
    evidence = tuple(
        _observation_evidence(fact, coding, facts) for fact, coding in current[:MAX_EVIDENCE]
    )
    compared: list[tuple[ObservationFact, _Interval, str]] = []
    unusable: Counter[str] = Counter()
    for fact, _ in current:
        interval, unit = _observed(fact, criterion)
        if interval is None:
            unusable[unit] += 1
        else:
            compared.append((fact, interval, unit))
    if unusable:
        return _Outcome(
            None,
            f"The most recent matching Observation ({when}) cannot be compared "
            f"({_reasons(unusable)}).",
            evidence,
        )
    target = _threshold(criterion)
    decisions = {_decide(interval, criterion) for _, interval, _ in compared}
    if len(decisions) > 1:
        return _Outcome(
            None,
            f"Matching Observations from the same date ({when}) disagree about {target}.",
            evidence,
        )
    decision = decisions.pop()
    fact, interval, unit = compared[0]
    recorded = _describe_observed(fact, interval, unit)
    if decision is None:
        rationale = (
            f"Most recent matching Observation ({when}): {recorded} cannot establish {target}."
        )
    else:
        verb = "satisfies" if decision else "does not satisfy"
        rationale = f"Most recent matching Observation ({when}): {recorded} {verb} {target}."
    return _Outcome(decision, rationale, evidence)


def _evaluate_status(criterion: Criterion, facts: PatientFacts) -> _Outcome:
    label = "pregnancy" if criterion.type == "pregnancy" else "breastfeeding"
    fact: StatusFact | None = (
        facts.pregnancy if criterion.type == "pregnancy" else facts.breastfeeding
    )
    if fact is None:
        flag = "pregnant" if criterion.type == "pregnancy" else "breastfeeding"
        return _Outcome(
            None,
            f"No {label} status documented (no coded status Observation and no "
            f"patient_context.{flag}).",
        )
    state = "pregnant" if criterion.type == "pregnancy" else "breastfeeding"
    word = {True: state, False: f"not {state}", None: "unknown"}[fact.value]
    if fact.source == "patient_context":
        evidence = Evidence(
            resource_type="patient_context",
            display=f"caller-asserted {label} status",
            value=fact.value,
        )
        source = "patient_context (caller-asserted)"
    else:
        evidence = Evidence(
            resource_type="Observation",
            system=fact.coding.system if fact.coding else None,
            code=fact.coding.code if fact.coding else None,
            display=fact.display,
            value=word,
            recorded=facts.exportable(fact.recorded),
        )
        if fact.recorded is None:
            source = "undated Observation"
        elif facts.exportable(fact.recorded) is None:
            source = f"Observation, {_WITHHELD}"
        else:
            source = f"Observation dated {fact.recorded.isoformat()}"
    if criterion.within_days is not None and fact.source != "patient_context":
        if fact.recorded is None:
            return _Outcome(None, f"The most recent {label} status is undated.", (evidence,))
        if _days_before(facts, fact.recorded) > criterion.within_days:
            return _Outcome(
                None,
                f"The most recent {label} status ({source}) is outside the "
                f"{criterion.within_days}-day window.",
                (evidence,),
            )
    if fact.value is None:
        return _Outcome(None, f"The most recent {label} status ({source}) is unknown.", (evidence,))
    return _Outcome(
        _apply_presence(criterion, fact.value),
        f"Documented as {word} ({source}).",
        (evidence,),
    )


def _evaluate_sex(criterion: Criterion, facts: PatientFacts) -> _Outcome:
    sex = facts.sex
    evidence = (Evidence(resource_type="Patient", display="administrative gender", value=sex),)
    if criterion.gender_based:
        return _Outcome(
            None,
            "Eligibility is based on gender identity (eligibilityModule.genderBased); FHIR "
            "administrative gender cannot decide it.",
            evidence,
            review=True,
        )
    if sex in {"female", "male"}:
        holds = sex.upper() == criterion.sex
        verb = "matches" if holds else "does not match"
        return _Outcome(
            holds,
            f"Recorded administrative gender '{sex}' {verb} the trial's sex {criterion.sex}.",
            evidence,
        )
    shown = sex or "missing"
    return _Outcome(
        None,
        f"Administrative gender is {shown}; it cannot establish the trial's sex {criterion.sex}.",
        evidence,
    )


def _reached(start: date, amount: int, unit: str, on: date) -> bool:
    """Whether ``amount`` units after ``start`` falls on or before ``on``."""
    try:
        return shift_by_age(start, amount, unit) <= on
    except OverflowError:
        return False  # after 9999-12-31, so after any as_of


def _evaluate_age(criterion: Criterion, facts: PatientFacts) -> _Outcome:
    limit = criterion.age_limit
    assert limit is not None
    if limit.unit in {"Hours", "Minutes"}:
        return _Outcome(
            None,
            f"A {limit.bound} age of {limit.text} cannot be evaluated from a birth date.",
            review=True,
        )
    years = facts.age_years()
    if facts.birth is None or years is None:
        return _Outcome(None, "No usable Patient.birthDate, so age cannot be evaluated.")
    shown = f"{years[0]} years" if years[0] == years[1] else f"{years[0]}-{years[1]} years"
    evidence = (
        Evidence(
            resource_type="Patient",
            display="age in completed years on as_of (birthDate is not returned)",
            value=Decimal(years[0]) if years[0] == years[1] else shown,
            unit="years" if years[0] == years[1] else None,
        ),
    )
    as_of, birth = facts.as_of, facts.birth
    holds: bool | None = None
    if limit.bound == "minimum":
        # Reached when even the latest possible birth date is old enough.
        if _reached(birth.latest, limit.amount, limit.unit, as_of):
            holds = True
        elif not _reached(birth.earliest, limit.amount, limit.unit, as_of):
            holds = False
        verdict = {True: "meets", False: "is below", None: "cannot be compared with"}[holds]
    else:
        # Inclusive maximum: the next anniversary (amount + 1) has not been reached yet.
        if not _reached(birth.earliest, limit.amount + 1, limit.unit, as_of):
            holds = True
        elif _reached(birth.latest, limit.amount + 1, limit.unit, as_of):
            holds = False
        verdict = {True: "is within", False: "is above", None: "cannot be compared with"}[holds]
    return _Outcome(
        holds,
        f"Age {shown} on {as_of.isoformat()} {verdict} the {limit.bound} age {limit.text} "
        "(inclusive).",
        evidence,
    )


def _evaluate_free_text(criterion: Criterion, facts: PatientFacts) -> _Outcome:
    return _Outcome(
        None,
        "Free-text criterion: never evaluated automatically; the study team must review it "
        "against the full record.",
        review=True,
    )


_EVALUATORS: dict[str, Callable[[Criterion, PatientFacts], _Outcome]] = {
    "condition": _evaluate_condition,
    "medication": _evaluate_medication,
    "lab": _evaluate_lab,
    "pregnancy": _evaluate_status,
    "lactation": _evaluate_status,
    "free_text": _evaluate_free_text,
    "sex": _evaluate_sex,
    "age": _evaluate_age,
}


def evaluate_criterion(criterion: Criterion, facts: PatientFacts) -> CriterionResult:
    """Decide one criterion against the patient's facts."""
    outcome = _EVALUATORS[criterion.type](criterion, facts)
    if outcome.review:
        status = REQUIRES_HUMAN_REVIEW
    elif outcome.holds is None:
        status = INSUFFICIENT_DATA
    else:
        status = MET if outcome.holds else NOT_MET
    return CriterionResult(criterion, status, outcome.rationale, outcome.evidence)


def evaluate_trial(trial: TrialDefinition, facts: PatientFacts) -> TrialResult:
    """Decide every criterion of a trial and derive its status (exclusions take precedence)."""
    results = tuple(evaluate_criterion(criterion, facts) for criterion in trial.criteria)
    blocking = tuple(
        sorted(
            (result for result in results if result.blocking),
            key=lambda result: result.criterion.section != EXCLUSION,
        )
    )
    open_results = tuple(result for result in results if result.open)
    if blocking:
        status = LIKELY_INELIGIBLE
    elif open_results:
        status = NEEDS_REVIEW
    else:
        status = POTENTIALLY_ELIGIBLE
    return TrialResult(trial, results, status, blocking, open_results)


def rank_trials(results: Sequence[TrialResult]) -> tuple[RankedTrial, ...]:
    """Rank trials deterministically and explain each position."""
    ordered = sorted(
        results,
        key=lambda result: (
            _STATUS_RANK[result.status],
            len(result.blocking),
            -result.score,
            len(result.open),
            result.trial.trial_id,
        ),
    )
    ranked: list[RankedTrial] = []
    for position, result in enumerate(ordered, start=1):
        reason = (
            f"{result.status}: {len(result.blocking)} blocking, {result.favourable} of "
            f"{len(result.results)} criteria favourable, {len(result.open)} open"
        )
        ranked.append(RankedTrial(position, result, reason))
    return tuple(ranked)
