"""De-identified patient facts for trial pre-screening, built on the MCP FHIR path.

The bundle first goes through the MCP ``parse_fhir_bundle`` tool, which rejects
bundles that mix patients or carry out-of-scope text and hashes the patient id.
The facts the trial criteria need beyond its output (condition and observation
codes, statuses, values, comparators, reference ranges and dates) are then read
from the same bundle with the same rules: invalidated resources (entered in
error, cancelled observations, refuted findings) are dropped, and only current
medications (``active``/``on-hold``) are kept and named by text or display.

Criteria are matched against the values as recorded (codes, units and word
tokens), so a patient whose name or id shares a token with a code or unit is
screened like anyone else. Every string that can leave this module is a
separate, de-identified copy made with the tool's de-identification (the
Patient's own names and identifiers, then ``sanitise_clinical_text``), and
clinical dates that fall on the patient's possible birth dates are withheld.
Patient.birthDate is used only to derive an age range and is never returned.
RESEARCH USE ONLY.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from medagent.mcp.tools import (
    TOOLS_BY_NAME,
    ToolInputError,
    _clean_text,
    _is_invalidated,
    _patient_redactor,
    _prepare_medication_resources,
    _require_single_patient,
    _select_medication_resources,
)
from medagent.safety.duplicate_therapy import DuplicateTherapyChecker
from medagent.safety.fhir_medication_request_adapter import FhirMedicationRequestAdapter
from medagent.trials.criteria import TrialInputError, phrase_tokens, shift_by_age
from medagent.trials.units import same_unit

_UCUM_SYSTEM = "http://unitsofmeasure.org"
_LOINC = "http://loinc.org"
_SNOMED = "http://snomed.info/sct"
_DATE_PREFIX = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
_PARTIAL_DATE = re.compile(r"([0-9]{4})(?:-([0-9]{2}))?")
_COMPARATORS = frozenset({"<", "<=", ">=", ">"})
_ACTIVE_CLINICAL_STATUSES = frozenset({"active", "recurrence", "relapse"})
_INACTIVE_CLINICAL_STATUSES = frozenset({"inactive", "remission", "resolved"})
_VERIFICATION_STATUSES = frozenset({"unconfirmed", "provisional", "differential", "confirmed"})
_MEDICATION_TYPES = frozenset({"MedicationRequest", "MedicationStatement"})

# Coded status observations (LOINC question -> answer code -> status; None = unknown).
_PREGNANCY_QUESTIONS = frozenset({(_LOINC, "82810-3"), (_LOINC, "11449-6")})
_PREGNANCY_ANSWERS: dict[tuple[str, str], bool | None] = {
    (_SNOMED, "77386006"): True,
    (_SNOMED, "60001007"): False,
    (_SNOMED, "152231000119106"): None,
    (_SNOMED, "261665006"): None,
}
_BREASTFEEDING_QUESTIONS = frozenset({(_LOINC, "63895-7")})
_BREASTFEEDING_ANSWERS: dict[tuple[str, str], bool | None] = {
    (_LOINC, "LA29252-6"): True,
    (_LOINC, "LA29253-4"): False,
}


def code_key(system: Any, code: Any) -> tuple[str, str] | None:
    """Normalised (system, code) used for matching: case-insensitive, no trailing ``/``."""
    if not isinstance(system, str) or not isinstance(code, str):
        return None
    normalised = system.strip().rstrip("/").lower(), code.strip().upper()
    return normalised if all(normalised) else None


@dataclass(frozen=True)
class Coding:
    """A coded concept: ``key`` is matched as recorded; ``system``/``code`` are for output."""

    key: tuple[str, str] | None
    system: str | None
    code: str | None


@dataclass(frozen=True)
class Concept:
    """A CodeableConcept: codings, de-identified names, and the recorded names' word tokens."""

    codings: tuple[Coding, ...]
    displays: tuple[str, ...]
    words: tuple[tuple[str, ...], ...]

    @property
    def keys(self) -> frozenset[tuple[str, str]]:
        """Every matchable (system, code) key."""
        return frozenset(coding.key for coding in self.codings if coding.key is not None)


@dataclass(frozen=True)
class ConditionFact:
    """A Condition: concept, statuses and onset date."""

    concept: Concept
    clinical_status: str | None
    verification_status: str | None
    onset: date | None


@dataclass(frozen=True)
class ObservationFact:
    """An Observation: concept, numeric value, reference upper limit and date.

    ``unit`` and ``reference_high_unit`` are as recorded (used for conversion);
    ``unit_label`` is the de-identified copy that is exported.
    """

    concept: Concept
    value: Decimal | None
    comparator: str | None
    unit: str | None
    unit_label: str | None
    value_codings: tuple[Coding, ...]
    reference_high: Decimal | None
    reference_high_unit: str | None
    effective: date | None


@dataclass(frozen=True)
class MedicationFact:
    """A current (active or on-hold) medication named by text or display.

    ``tokens`` and ``rxnorm_key`` are matched; ``name`` and ``rxnorm_code`` are
    the de-identified copies that are exported.
    """

    resource_type: str
    name: str
    tokens: frozenset[str]
    rxnorm_key: str | None
    rxnorm_code: str | None
    recorded: date | None


@dataclass(frozen=True)
class StatusFact:
    """Pregnancy or breastfeeding status; ``value`` None means documented as unknown."""

    value: bool | None
    source: str
    recorded: date | None
    coding: Coding | None = None
    display: str | None = None


@dataclass(frozen=True)
class BirthRange:
    """Earliest and latest possible birth dates (equal for a full birthDate)."""

    earliest: date
    latest: date


@dataclass(frozen=True)
class ConceptIndex:
    """Positions of the facts that carry each code key and each word.

    ``codes_by_system`` lists each system's codes in sorted order, so prefix
    matches are found by bisection instead of a scan of every fact.
    """

    by_key: Mapping[tuple[str, str], tuple[int, ...]]
    by_word: Mapping[str, tuple[int, ...]]
    codes_by_system: Mapping[str, tuple[str, ...]]

    @classmethod
    def build(cls, concepts: Sequence[Concept]) -> ConceptIndex:
        """Index ``concepts`` by position."""
        by_key: defaultdict[tuple[str, str], list[int]] = defaultdict(list)
        by_word: defaultdict[str, list[int]] = defaultdict(list)
        for position, concept in enumerate(concepts):
            for key in concept.keys:
                by_key[key].append(position)
            for word in {word for words in concept.words for word in words}:
                by_word[word].append(position)
        codes: defaultdict[str, list[str]] = defaultdict(list)
        for system, code in by_key:
            codes[system].append(code)
        return cls(
            by_key={key: tuple(value) for key, value in by_key.items()},
            by_word={word: tuple(value) for word, value in by_word.items()},
            codes_by_system={system: tuple(sorted(value)) for system, value in codes.items()},
        )


@dataclass(frozen=True)
class PatientFacts:
    """Everything the evaluator may use about one patient.

    Exported strings are de-identified copies; matching keys and tokens never
    leave the evaluator.
    """

    as_of: date
    patient_id_hash: str
    sex: str | None
    birth: BirthRange | None
    conditions: tuple[ConditionFact, ...]
    condition_resources: int
    condition_index: ConceptIndex
    medications: tuple[MedicationFact, ...]
    medication_resources: int
    unnamed_current_medications: int
    observations: tuple[ObservationFact, ...]
    observation_resources: int
    observation_index: ConceptIndex
    pregnancy: StatusFact | None
    breastfeeding: StatusFact | None
    notes: tuple[str, ...]

    def age_years(self) -> tuple[int, int] | None:
        """Completed years of age on ``as_of`` as a (min, max) range, if known."""
        if self.birth is None:
            return None
        return (
            completed_years(self.birth.latest, self.as_of),
            completed_years(self.birth.earliest, self.as_of),
        )

    def exportable(self, value: date | None) -> date | None:
        """``value``, or None when it could reveal the date of birth."""
        if value is None or self.birth is None:
            return value
        return None if self.birth.earliest <= value <= self.birth.latest else value


def completed_years(born: date, on: date) -> int:
    """Whole years reached on ``on``, with the anniversary rule used for age limits."""
    years = on.year - born.year
    try:
        if shift_by_age(born, years, "Years") > on:
            years -= 1
    except ValueError:
        years -= 1
    return max(years, 0)


def _date(value: Any) -> date | None:
    """The calendar date of a FHIR date/dateTime with day precision, else None."""
    match = _DATE_PREFIX.match(value) if isinstance(value, str) else None
    if match is None:
        return None
    try:
        return date(int(match[1]), int(match[2]), int(match[3]))
    except ValueError:
        return None


def _birth_range(birth_date: Any, as_of: date) -> BirthRange | None:
    """Possible birth dates for a full or partial FHIR birthDate (YYYY, YYYY-MM)."""
    exact = _date(birth_date)
    if exact is not None:
        return BirthRange(exact, exact) if exact <= as_of else None
    match = _PARTIAL_DATE.fullmatch(birth_date) if isinstance(birth_date, str) else None
    if match is None:
        return None
    year = int(match[1])
    try:
        if match[2] is None:
            earliest, latest = date(year, 1, 1), date(year, 12, 31)
        else:
            month = int(match[2])
            earliest = date(year, month, 1)
            following = date(year + month // 12, month % 12 + 1, 1)
            latest = date.fromordinal(following.toordinal() - 1)
    except ValueError:
        return None
    if earliest > as_of:
        return None
    return BirthRange(earliest, min(latest, as_of))


def _number(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return Decimal(str(value))


def _quantity_unit(quantity: Mapping[str, Any]) -> str | None:
    """The unit to convert with: the UCUM code wins over a display unit that differs.

    A display unit is kept when it denotes the same unit as the UCUM code (so
    ``mL/s/1.73m2`` is shown instead of ``mL/s/{1.73_m2}``).
    """
    code = quantity.get("code")
    unit = quantity.get("unit")
    display = unit if isinstance(unit, str) and unit.strip() else None
    if quantity.get("system") == _UCUM_SYSTEM and isinstance(code, str) and code.strip():
        return display if display and same_unit(code, display) else code
    return display


class _FactReader:
    """Reads facts from validated bundle entries, with de-identified copies for output."""

    def __init__(self, clean: Callable[[str], str]) -> None:
        self._clean = clean

    def text(self, value: Any) -> str | None:
        """A de-identified copy of a string, for output."""
        if not isinstance(value, str) or not value.strip():
            return None
        cleaned = self._clean(value)
        return cleaned or None

    def concept(self, concept: Any) -> Concept:
        """Codings, distinct de-identified names and recorded word tokens of a concept."""
        if not isinstance(concept, dict):
            return Concept((), (), ())
        codings: list[Coding] = []
        names: list[Any] = [concept.get("text")]
        raw_codings = concept.get("coding")
        for coding in raw_codings if isinstance(raw_codings, list) else []:
            if not isinstance(coding, dict):
                continue
            system, code = coding.get("system"), coding.get("code")
            codings.append(Coding(code_key(system, code), self.text(system), self.text(code)))
            names.append(coding.get("display"))
        recorded = [name for name in names if isinstance(name, str) and name.strip()]
        displays: list[str] = []
        for name in recorded:
            cleaned = self.text(name)
            if cleaned and cleaned not in displays:
                displays.append(cleaned)
        return Concept(
            codings=tuple(codings),
            displays=tuple(displays),
            words=tuple(phrase_tokens(name) for name in dict.fromkeys(recorded)),
        )

    @staticmethod
    def status_code(concept: Any, allowed: frozenset[str]) -> str | None:
        """First recognised code of a status CodeableConcept, else 'unrecognized'/None."""
        if not isinstance(concept, dict):
            return None
        codings = concept.get("coding")
        codes = [
            str(coding.get("code")).lower()
            for coding in (codings if isinstance(codings, list) else [])
            if isinstance(coding, dict) and isinstance(coding.get("code"), str)
        ]
        if not codes:
            return None
        return next((code for code in codes if code in allowed), "unrecognized")

    def condition(self, resource: Mapping[str, Any]) -> ConditionFact:
        onset = _date(resource.get("onsetDateTime"))
        period = resource.get("onsetPeriod")
        if onset is None and isinstance(period, dict):
            onset = _date(period.get("start"))
        return ConditionFact(
            concept=self.concept(resource.get("code")),
            clinical_status=self.status_code(
                resource.get("clinicalStatus"),
                _ACTIVE_CLINICAL_STATUSES | _INACTIVE_CLINICAL_STATUSES,
            ),
            verification_status=self.status_code(
                resource.get("verificationStatus"), _VERIFICATION_STATUSES
            ),
            onset=onset,
        )

    def observation(self, resource: Mapping[str, Any]) -> ObservationFact:
        quantity = resource.get("valueQuantity")
        quantity = quantity if isinstance(quantity, dict) else {}
        comparator = quantity.get("comparator")
        value = _number(quantity.get("value"))
        if comparator is not None and comparator not in _COMPARATORS:
            value = None  # e.g. "ad": not a measured amount
        reference_high: Decimal | None = None
        reference_unit: str | None = None
        ranges = resource.get("referenceRange")
        first = ranges[0] if isinstance(ranges, list) and ranges else None
        high = first.get("high") if isinstance(first, dict) else None
        if isinstance(high, dict):
            reference_high = _number(high.get("value"))
            reference_unit = _quantity_unit(high)
        effective = _date(resource.get("effectiveDateTime"))
        period = resource.get("effectivePeriod")
        if effective is None and isinstance(period, dict):
            effective = _date(period.get("end")) or _date(period.get("start"))
        effective = effective or _date(resource.get("effectiveInstant"))
        effective = effective or _date(resource.get("issued"))
        unit = _quantity_unit(quantity)
        return ObservationFact(
            concept=self.concept(resource.get("code")),
            value=value,
            comparator=comparator if value is not None and comparator in _COMPARATORS else None,
            unit=unit,
            unit_label=self.text(unit),
            value_codings=self.concept(resource.get("valueCodeableConcept")).codings,
            reference_high=reference_high,
            reference_high_unit=reference_unit,
            effective=effective,
        )


def _medication_date(resource: Mapping[str, Any]) -> date | None:
    period = resource.get("effectivePeriod")
    return (
        _date(resource.get("authoredOn"))
        or _date(resource.get("effectiveDateTime"))
        or (_date(period.get("start")) if isinstance(period, dict) else None)
        or _date(resource.get("dateAsserted"))
    )


def _latest_status(
    observations: tuple[ObservationFact, ...],
    as_of: date,
    questions: frozenset[tuple[str, str]],
    answers: Mapping[tuple[str, str], bool | None],
    notes: list[str],
    label: str,
) -> StatusFact | None:
    """The latest coded status answer on or before ``as_of``; same-day conflicts are unknown."""
    found: list[tuple[date | None, bool | None, Coding, str | None]] = []
    unrecognised = later = 0
    for fact in observations:
        if not fact.concept.keys & questions:
            continue
        if fact.effective is not None and fact.effective > as_of:
            later += 1
            continue
        answer = next(
            (coding for coding in fact.value_codings if coding.key in answers),
            None,
        )
        if answer is None or answer.key is None:
            unrecognised += 1
            continue
        display = fact.concept.displays[0] if fact.concept.displays else None
        found.append((fact.effective, answers[answer.key], answer, display))
    if unrecognised:
        notes.append(
            f"ignored {unrecognised} {label} observation(s) without a recognised coded answer"
        )
    if later:
        notes.append(f"ignored {later} {label} observation(s) dated after as_of")
    if not found:
        return None
    dates: list[date] = [item[0] for item in found if item[0] is not None]
    latest = max(dates, default=None)
    current = [item for item in found if item[0] == latest]
    values = {item[1] for item in current}
    if len(values) > 1:
        notes.append(f"conflicting {label} observations on the same date; treated as unknown")
    value = values.pop() if len(values) == 1 else None
    _, _, coding, display = current[0]
    return StatusFact(
        value=value, source="Observation", recorded=latest, coding=coding, display=display
    )


def extract_patient_facts(
    bundle: Mapping[str, Any],
    *,
    as_of: date,
    patient_context: Mapping[str, Any] | None = None,
) -> PatientFacts:
    """Build de-identified facts for one patient from a FHIR R4 Bundle.

    Args:
        bundle: Schema-valid FHIR R4 Bundle describing one patient.
        as_of: Evaluation date for the age range and status observations.
        patient_context: Optional caller-asserted ``pregnant`` / ``breastfeeding``
            flags; they take precedence over coded status observations.

    Returns:
        The patient's facts, without names, identifiers, dates of birth or the raw bundle.

    Raises:
        TrialInputError: When the MCP FHIR path rejects the bundle (several
            patients, scope violation, unexpected structure).
    """
    try:
        return _extract(bundle, as_of, patient_context or {})
    except ToolInputError as exc:
        # Messages are fixed text plus counts (see medagent.mcp.tools); no caller text.
        raise TrialInputError("fhir_rejected", f"FHIR data rejected: {exc}") from None
    except (AttributeError, LookupError, TypeError, ValueError) as exc:
        raise TrialInputError(
            "fhir_rejected",
            "FHIR data could not be parsed: a resource has an unexpected structure "
            f"({type(exc).__name__}).",
        ) from None


def _extract(
    bundle: Mapping[str, Any], as_of: date, patient_context: Mapping[str, Any]
) -> PatientFacts:
    parsed = TOOLS_BY_NAME["parse_fhir_bundle"].handler({"bundle": dict(bundle)}).structured
    all_entries: list[dict[str, Any]] = list(bundle.get("entry", []))
    patient = _require_single_patient(all_entries)
    entries = [entry for entry in all_entries if not _is_invalidated(entry.get("resource", {}))]
    redact_patient = _patient_redactor(patient)

    def clean(text: str) -> str:
        return _clean_text(redact_patient(text))

    reader = _FactReader(clean)
    notes: list[str] = []
    invalidated = len(all_entries) - len(entries)
    if invalidated:
        notes.append(
            f"excluded {invalidated} invalidated resource(s) (entered-in-error, cancelled "
            "observations or refuted findings)"
        )
    counts: Counter[str] = Counter()
    conditions: list[ConditionFact] = []
    observations: list[ObservationFact] = []
    for entry in entries:
        resource = entry.get("resource", {})
        resource_type = resource.get("resourceType")
        if resource_type == "Condition":
            counts["Condition"] += 1
            conditions.append(reader.condition(resource))
        elif resource_type == "Observation":
            counts["Observation"] += 1
            observations.append(reader.observation(resource))
        elif resource_type in _MEDICATION_TYPES:
            counts["Medication"] += 1

    selected, status_notes = _select_medication_resources(entries, include_proposed=False)
    notes.extend(status_notes)
    medications: list[MedicationFact] = []
    unnamed = 0
    for entry, prepared in zip(
        selected, _prepare_medication_resources(selected, entries), strict=True
    ):
        name, rxnorm, _ = FhirMedicationRequestAdapter._extract_name(prepared)
        cleaned_name = reader.text(name)
        if not isinstance(name, str) or not cleaned_name:
            unnamed += 1
            continue
        resource = entry.get("resource", {})
        medications.append(
            MedicationFact(
                resource_type=str(resource.get("resourceType")),
                name=cleaned_name,
                tokens=frozenset(DuplicateTherapyChecker._tokens(name)),
                rxnorm_key=rxnorm.strip() if isinstance(rxnorm, str) else None,
                rxnorm_code=reader.text(rxnorm),
                recorded=_medication_date(resource),
            )
        )
    if unnamed:
        notes.append(
            f"{unnamed} current medication(s) could not be named (code-only or unresolvable "
            "reference), so medication criteria cannot confirm their absence"
        )

    birth = _birth_range(patient.get("birthDate") if patient else None, as_of)
    if birth is None:
        notes.append("no usable Patient.birthDate: age limits cannot be evaluated")
    elif birth.earliest != birth.latest:
        notes.append("Patient.birthDate is a partial date: age is known only as a range")

    observation_facts = tuple(observations)
    pregnancy = _latest_status(
        observation_facts,
        as_of,
        _PREGNANCY_QUESTIONS,
        _PREGNANCY_ANSWERS,
        notes,
        "pregnancy status",
    )
    breastfeeding = _latest_status(
        observation_facts,
        as_of,
        _BREASTFEEDING_QUESTIONS,
        _BREASTFEEDING_ANSWERS,
        notes,
        "breastfeeding status",
    )
    if isinstance(patient_context.get("pregnant"), bool):
        pregnancy = StatusFact(patient_context["pregnant"], "patient_context", as_of)
        notes.append("pregnancy status taken from patient_context (caller-asserted)")
    if isinstance(patient_context.get("breastfeeding"), bool):
        breastfeeding = StatusFact(patient_context["breastfeeding"], "patient_context", as_of)
        notes.append("breastfeeding status taken from patient_context (caller-asserted)")

    condition_facts = tuple(conditions)
    return PatientFacts(
        as_of=as_of,
        patient_id_hash=str(parsed["patient_id_hash"]),
        sex=parsed["sex"],
        birth=birth,
        conditions=condition_facts,
        condition_resources=counts["Condition"],
        condition_index=ConceptIndex.build([fact.concept for fact in condition_facts]),
        medications=tuple(medications),
        medication_resources=counts["Medication"],
        unnamed_current_medications=unnamed,
        observations=observation_facts,
        observation_resources=counts["Observation"],
        observation_index=ConceptIndex.build([fact.concept for fact in observation_facts]),
        pregnancy=pregnancy,
        breastfeeding=breastfeeding,
        notes=tuple(notes),
    )
