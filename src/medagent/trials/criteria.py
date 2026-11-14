"""Trial definitions: parsing and semantic validation of the trial-criteria format 1.0.

The JSON Schemas in :mod:`medagent.trials.schema` check structure; this module
enforces what a schema cannot express (which fields each criterion type accepts,
units, ranges, unique ids, ClinicalTrials.gov ``NormalizedTime`` ages) and turns
each definition into immutable :class:`TrialDefinition` objects.

``eligibilityModule.sex``, ``minimumAge`` and ``maximumAge`` become derived
inclusion criteria (``eligibility.sex``, ``eligibility.minimum_age``,
``eligibility.maximum_age``). Error messages name schema paths and positions,
never caller-supplied values. RESEARCH USE ONLY.
"""

from __future__ import annotations

import calendar
import math
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from medagent.llm.validator import redact_prohibited_language
from medagent.logging_config import get_logger
from medagent.safety.duplicate_therapy import DuplicateTherapyChecker
from medagent.safety.scope_enforcer import ScopeEnforcer
from medagent.trials.schema import (
    DATE_PATTERN,
    EXCLUSION,
    ID_PATTERN,
    INCLUSION,
    RESERVED_ID_PREFIX,
    VERSION_PATTERN,
)
from medagent.trials.units import is_supported_unit

logger = get_logger(__name__)

_COMMON_FIELDS = frozenset({"id", "type", "text"})
_ALLOWED_FIELDS: dict[str, frozenset[str]] = {
    "condition": frozenset({"codes", "terms", "presence", "status", "within_days"}),
    "medication": frozenset({"ingredients", "classes", "rxnorm_codes", "presence"}),
    "lab": frozenset(
        {"codes", "terms", "operator", "value", "low", "high", "unit", "relative_to"}
        | {"within_days"}
    ),
    "pregnancy": frozenset({"presence", "within_days"}),
    "lactation": frozenset({"presence", "within_days"}),
    "free_text": frozenset(),
}
_AGE = re.compile(r"(?P<amount>[0-9]{1,3}) (?P<unit>Year|Month|Week|Day|Hour|Minute)s?")
_RXNORM = re.compile(r"[0-9]{1,10}")
_WORD = re.compile(r"[^\W_]+")
_MAX_MAGNITUDE = Decimal("1e15")
_SCOPE_ENFORCER = ScopeEnforcer()


class TrialInputError(ValueError):
    """Screening input that the caller can correct (HTTP 422, MCP ``isError``).

    Messages are fixed text plus schema paths and counts; they never contain
    caller-supplied values.
    """

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class CodeRef:
    """A coded concept a criterion matches (``prefix`` also matches longer codes)."""

    system: str
    code: str
    prefix: bool = False


@dataclass(frozen=True)
class AgeLimit:
    """A ClinicalTrials.gov ``minimumAge`` / ``maximumAge`` limit (always inclusive)."""

    bound: str
    amount: int
    unit: str

    @property
    def text(self) -> str:
        """The limit in ClinicalTrials.gov form, e.g. ``18 Years``."""
        return f"{self.amount} {self.unit}"


@dataclass(frozen=True)
class Criterion:
    """One structured (or free-text) criterion of a trial, ready to evaluate."""

    id: str
    section: str
    type: str
    text: str
    presence: str = "present"
    condition_status: str = "any"
    codes: tuple[CodeRef, ...] = ()
    terms: tuple[tuple[str, ...], ...] = ()
    ingredients: tuple[tuple[str, frozenset[str]], ...] = ()
    classes: tuple[str, ...] = ()
    rxnorm_codes: frozenset[str] = frozenset()
    operator: str | None = None
    value: Decimal | None = None
    low: Decimal | None = None
    high: Decimal | None = None
    unit: str | None = None
    relative_to: str | None = None
    within_days: int | None = None
    age_limit: AgeLimit | None = None
    sex: str | None = None
    gender_based: bool = False


@dataclass(frozen=True)
class TrialDefinition:
    """A validated trial definition: derived criteria first, then inclusion, then exclusion."""

    trial_id: str
    version: str
    title: str
    eligibility: Mapping[str, Any]
    criteria: tuple[Criterion, ...]


def display_text(text: str) -> str:
    """One line of text without control characters and with prescription phrasing neutralised."""
    cleaned = "".join(" " if unicodedata.category(char) in {"Cc", "Cf"} else char for char in text)
    return redact_prohibited_language(" ".join(cleaned.split()))


def phrase_tokens(text: str) -> tuple[str, ...]:
    """Case-folded word tokens used to match condition and lab terms."""
    return tuple(_WORD.findall(text.casefold()))


def parse_as_of(value: str | None) -> date | None:
    """Parse an ``as_of`` argument (``YYYY-MM-DD``); None when it is not given."""
    if value is None:
        return None
    if not re.fullmatch(DATE_PATTERN.strip("^$"), value):
        raise TrialInputError("invalid_arguments", "as_of must be a date in YYYY-MM-DD form.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise TrialInputError(
            "invalid_arguments", "as_of must be a valid calendar date (YYYY-MM-DD)."
        ) from None


def shift_by_age(start: date, amount: int, unit: str) -> date:
    """Return ``start`` plus ``amount`` calendar years, months, weeks or days.

    Anniversaries fall on the last day of shorter months, so 29 February falls on
    28 February in common years.

    Raises:
        OverflowError: When the result is after 9999-12-31.
    """
    if unit in {"Years", "Months"}:
        months = amount * 12 if unit == "Years" else amount
        year, month = divmod(start.month - 1 + months, 12)
        target_year, target_month = start.year + year, month + 1
        if target_year > date.max.year:
            raise OverflowError("date after 9999-12-31")
        last_day = calendar.monthrange(target_year, target_month)[1]
        return date(target_year, target_month, min(start.day, last_day))
    days = amount * 7 if unit == "Weeks" else amount
    if unit not in {"Weeks", "Days"}:
        raise ValueError(f"unsupported calendar unit: {unit}")
    if days > (date.max - start).days:
        raise OverflowError("date after 9999-12-31")
    return start + timedelta(days=days)


def _fail(path: str, message: str, reason: str = "invalid_trial") -> TrialInputError:
    return TrialInputError(reason, f"{path} {message}")


def _check_scope(texts: Sequence[str]) -> None:
    """Apply the agent's scope patterns (SAFETY.md §3.6) without logging any text."""
    for text in texts:
        pattern = _SCOPE_ENFORCER.find_violation(text)
        if pattern is not None:
            logger.warning("trial_scope_violation", pattern=pattern)
            raise TrialInputError(
                "scope_violation",
                "Input rejected by scope enforcement (SAFETY.md §3.6): trial text must not "
                "request browsing, code execution or non-clinical tasks.",
            )


def _decimal(raw: Any, path: str) -> Decimal:
    """A threshold as an exact decimal; numbers beyond +/-10^15 are rejected."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise _fail(path, "must be a number.")
    if isinstance(raw, float) and not math.isfinite(raw):
        raise _fail(path, "must be a finite number.")
    try:
        value = Decimal(str(raw))
    except ValueError:  # integers too long to convert to text
        value = _MAX_MAGNITUDE * 2
    if abs(value) > _MAX_MAGNITUDE:
        raise _fail(path, "must be between -1e15 and 1e15.")
    return value


def _parse_age(raw: Any, bound: str, path: str) -> AgeLimit | None:
    if raw is None or raw == "N/A":
        return None
    match = _AGE.fullmatch(raw) if isinstance(raw, str) else None
    if match is None:
        raise _fail(path, "must be a ClinicalTrials.gov age such as '18 Years', or 'N/A'.")
    return AgeLimit(bound=bound, amount=int(match["amount"]), unit=f"{match['unit']}s")


def _limit_instant(limit: AgeLimit) -> datetime:
    """A comparable instant for sanity-checking minimum <= maximum."""
    start = datetime(2001, 1, 1)
    if limit.unit == "Hours":
        return start + timedelta(hours=limit.amount)
    if limit.unit == "Minutes":
        return start + timedelta(minutes=limit.amount)
    shifted = shift_by_age(start.date(), limit.amount, limit.unit)
    return datetime(shifted.year, shifted.month, shifted.day)


def _derived_criteria(module: Mapping[str, Any], path: str) -> list[Criterion]:
    """Turn the eligibilityModule's sex and age limits into inclusion criteria."""
    criteria: list[Criterion] = []
    sex = module.get("sex")
    if sex in {"FEMALE", "MALE"}:
        criteria.append(
            Criterion(
                id=f"{RESERVED_ID_PREFIX}sex",
                section=INCLUSION,
                type="sex",
                text=f"Sex: {sex} (eligibilityModule.sex)",
                sex=str(sex),
                gender_based=bool(module.get("genderBased", False)),
            )
        )
    minimum = _parse_age(module.get("minimumAge"), "minimum", f"{path}.minimumAge")
    maximum = _parse_age(module.get("maximumAge"), "maximum", f"{path}.maximumAge")
    if minimum and maximum and _limit_instant(minimum) > _limit_instant(maximum):
        raise _fail(path, "has a minimumAge greater than its maximumAge.")
    for limit in (minimum, maximum):
        if limit is not None:
            criteria.append(
                Criterion(
                    id=f"{RESERVED_ID_PREFIX}{limit.bound}_age",
                    section=INCLUSION,
                    type="age",
                    text=f"{limit.bound.capitalize()} age: {limit.text} (inclusive)",
                    age_limit=limit,
                )
            )
    return criteria


def _code_refs(
    raw: Sequence[Mapping[str, Any]], path: str, *, allow_prefix: bool
) -> tuple[CodeRef, ...]:
    refs: list[CodeRef] = []
    for index, item in enumerate(raw):
        prefix = item.get("match") == "prefix"
        if prefix and not allow_prefix:
            raise _fail(f"{path}.codes[{index}].match", "'prefix' is only allowed for conditions.")
        refs.append(
            CodeRef(
                system=str(item["system"]).strip().rstrip("/").lower(),
                code=str(item["code"]).strip().upper(),
                prefix=prefix,
            )
        )
    return tuple(refs)


def _terms(raw: Sequence[str], path: str) -> tuple[tuple[str, ...], ...]:
    terms = tuple(phrase_tokens(term) for term in raw)
    if any(not tokens for tokens in terms):
        raise _fail(f"{path}.terms", "must contain letters or digits.")
    return terms


def _parse_criterion(raw: Mapping[str, Any], section: str, path: str) -> Criterion:
    """Validate one criterion against the per-type rules and return it."""
    kind = str(raw["type"])
    criterion_id = str(raw["id"])
    if not re.fullmatch(ID_PATTERN.strip("^$"), criterion_id):
        raise _fail(f"{path}.id", "must match the id pattern.")
    if criterion_id.startswith(RESERVED_ID_PREFIX):
        raise _fail(
            f"{path}.id", f"must not start with the reserved prefix '{RESERVED_ID_PREFIX}'."
        )
    extra = sorted(set(raw) - _COMMON_FIELDS - _ALLOWED_FIELDS[kind])
    if extra:
        raise _fail(path, f"(type {kind}) does not accept: {', '.join(extra)}.")
    fields: dict[str, Any] = {
        "id": criterion_id,
        "section": section,
        "type": kind,
        "text": display_text(str(raw["text"])),
        "presence": str(raw.get("presence", "present")),
        "condition_status": str(raw.get("status", "any")),
        "within_days": raw.get("within_days"),
    }
    if kind in {"condition", "lab"}:
        if "codes" not in raw and "terms" not in raw:
            raise _fail(path, f"(type {kind}) needs codes and/or terms.")
        fields["codes"] = _code_refs(raw.get("codes", []), path, allow_prefix=kind == "condition")
        fields["terms"] = _terms(raw.get("terms", []), path)
    if kind == "medication":
        if not {"ingredients", "classes", "rxnorm_codes"} & set(raw):
            raise _fail(path, "(type medication) needs ingredients, classes and/or rxnorm_codes.")
        ingredients = tuple(
            (display_text(name), frozenset(DuplicateTherapyChecker._tokens(name)))
            for name in raw.get("ingredients", [])
        )
        if any(not tokens for _, tokens in ingredients):
            raise _fail(f"{path}.ingredients", "must contain letters or digits.")
        codes = [str(code) for code in raw.get("rxnorm_codes", [])]
        if any(not _RXNORM.fullmatch(code) for code in codes):
            raise _fail(f"{path}.rxnorm_codes", "must be numeric RxNorm codes.")
        fields.update(
            ingredients=ingredients,
            classes=tuple(str(name) for name in raw.get("classes", [])),
            rxnorm_codes=frozenset(codes),
        )
    if kind == "lab":
        fields.update(_lab_fields(raw, path))
    return Criterion(**fields)


def _lab_fields(raw: Mapping[str, Any], path: str) -> dict[str, Any]:
    """Validate a lab criterion's comparison and return its typed fields."""
    operator = raw.get("operator")
    if operator is None:
        raise _fail(path, "(type lab) needs an operator.")
    fields: dict[str, Any] = {"operator": str(operator), "relative_to": raw.get("relative_to")}
    if operator == "between":
        if "low" not in raw or "high" not in raw or "value" in raw:
            raise _fail(path, "(operator between) needs low and high, and no value.")
        fields["low"] = _decimal(raw["low"], f"{path}.low")
        fields["high"] = _decimal(raw["high"], f"{path}.high")
        if fields["low"] > fields["high"]:
            raise _fail(path, "has low greater than high.")
    else:
        if "value" not in raw or "low" in raw or "high" in raw:
            raise _fail(path, f"(operator {operator}) needs a value, and no low or high.")
        fields["value"] = _decimal(raw["value"], f"{path}.value")
    if fields["relative_to"] is not None:
        if "unit" in raw:
            raise _fail(path, "with relative_to compares multiples of the limit and takes no unit.")
    elif "unit" not in raw:
        raise _fail(path, "(type lab) needs a unit, or relative_to.")
    elif not is_supported_unit(str(raw["unit"])):
        raise _fail(f"{path}.unit", "is not a supported unit (see the unit table in the guide).")
    else:
        fields["unit"] = str(raw["unit"])
    return fields


def parse_trial(raw: Mapping[str, Any], index: int) -> TrialDefinition:
    """Validate one schema-valid trial definition.

    Args:
        raw: A trial definition that already conforms to ``TRIAL_SCHEMA``.
        index: Position in the request, used in error paths.

    Returns:
        The immutable trial definition.

    Raises:
        TrialInputError: When the definition breaks a rule the schema cannot express.
    """
    path = f"trials[{index}]"
    trial_id = str(raw["trial_id"])
    if not re.fullmatch(ID_PATTERN.strip("^$"), trial_id):
        raise _fail(f"{path}.trial_id", "must match the id pattern.")
    if not re.fullmatch(VERSION_PATTERN.strip("^$"), str(raw["version"])):
        raise _fail(f"{path}.version", "must match the version pattern.")
    module: Mapping[str, Any] = raw.get("eligibilityModule", {})
    _check_scope(
        [
            str(raw["title"]),
            *(str(module.get(key, "")) for key in ("eligibilityCriteria", "genderDescription")),
            str(module.get("studyPopulation", "")),
            *(
                str(text)
                for section in (INCLUSION, EXCLUSION)
                for criterion in raw.get(section, [])
                for text in (
                    criterion.get("text", ""),
                    *criterion.get("terms", []),
                    *criterion.get("ingredients", []),
                )
            ),
        ]
    )
    criteria = _derived_criteria(module, f"{path}.eligibilityModule")
    for section in (INCLUSION, EXCLUSION):
        for position, item in enumerate(raw.get(section, [])):
            criteria.append(_parse_criterion(item, section, f"{path}.{section}[{position}]"))
    seen: set[str] = set()
    for criterion in criteria:
        if criterion.id in seen:
            raise _fail(path, "has duplicate criterion ids; ids must be unique within a trial.")
        seen.add(criterion.id)
    if not criteria:
        raise _fail(
            path,
            "has nothing to evaluate: add eligibilityModule sex or age limits, or inclusion or "
            "exclusion criteria.",
            reason="empty_trial",
        )
    eligibility = {
        "sex": module.get("sex"),
        "minimumAge": module.get("minimumAge"),
        "maximumAge": module.get("maximumAge"),
        "healthyVolunteers": module.get("healthyVolunteers"),
        "genderBased": module.get("genderBased"),
        "stdAges": list(module.get("stdAges", [])),
        "source_criteria_text_supplied": bool(str(module.get("eligibilityCriteria", "")).strip()),
    }
    return TrialDefinition(
        trial_id=trial_id,
        version=str(raw["version"]),
        title=display_text(str(raw["title"])),
        eligibility=eligibility,
        criteria=tuple(criteria),
    )


def parse_trials(raw_trials: Sequence[Mapping[str, Any]]) -> tuple[TrialDefinition, ...]:
    """Validate every trial definition of a request; trial ids must be unique."""
    trials = tuple(parse_trial(raw, index) for index, raw in enumerate(raw_trials))
    ids = [trial.trial_id for trial in trials]
    if len(set(ids)) != len(ids):
        raise TrialInputError(
            "duplicate_trial", "trials contain duplicate trial_id values; send each trial once."
        )
    return trials
