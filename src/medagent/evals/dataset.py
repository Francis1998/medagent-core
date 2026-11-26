"""Typed rubric dataset and response formats (HealthBench JSONL compatible).

Dataset rows follow OpenAI HealthBench's JSONL, one example per line::

    {"prompt_id": "...", "prompt": [{"role": "user", "content": "..."}],
     "rubrics": [{"criterion": "...", "points": 9, "tags": ["axis:completeness"]}],
     "example_tags": ["theme:emergency_referrals"]}

Unknown top-level keys (HealthBench's ``ideal_completions_data`` and
``canary``) are ignored, so HealthBench files load unchanged. medagent adds one
optional key per rubric item, ``check``: a machine-checkable spec that
:mod:`medagent.evals.grader` evaluates deterministically. Criteria without a
check stay ``ungraded``. Response files are JSONL rows
``{"prompt_id": "...", "response": "..."}``.

Validation errors name the file, line and field path but never echo prompt or
response text, so they are safe to print and to log.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

MAX_EXAMPLES = 10_000
MAX_MESSAGES = 100
MAX_MESSAGE_CHARS = 100_000
MAX_RESPONSE_CHARS = 50_000
MAX_CRITERIA_PER_EXAMPLE = 200
MAX_CRITERION_CHARS = 5_000
MAX_ABS_POINTS = 100.0
MAX_TAGS = 50
MAX_PATTERNS = 20
MAX_PATTERN_CHARS = 300
MAX_WORDS_LIMIT = 100_000

ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
_TAG_RE = re.compile(r"^\S{1,200}$")

AXIS_PREFIX = "axis:"
THEME_PREFIX = "theme:"

CHECK_TYPES: tuple[str, ...] = (
    "pattern",
    "disclaimer",
    "clinician_referral",
    "emergency_care",
    "dose_directive",
    "clarifying_question",
    "length",
)


class RubricDatasetError(ValueError):
    """A dataset or responses file is unreadable or invalid.

    Args:
        source: File path (or other label) of the input.
        line: 1-based line number, or ``None`` for file-level problems.
        detail: What is wrong, naming field paths but never input text.
    """

    def __init__(self, source: str, line: int | None, detail: str) -> None:
        location = f"{source}:{line}" if line is not None else source
        super().__init__(f"{location}: {detail}")
        self.source = source
        self.line = line
        self.detail = detail


def _validate_patterns(patterns: list[str]) -> list[str]:
    """Reject empty, oversized or uncompilable regular expressions."""
    for index, pattern in enumerate(patterns):
        if not pattern or len(pattern) > MAX_PATTERN_CHARS:
            raise ValueError(f"pattern {index} must be 1-{MAX_PATTERN_CHARS} characters")
        try:
            re.compile(pattern, re.IGNORECASE)
        except re.error as exc:
            detail = f"pattern {index} is not a valid regular expression ({exc.msg})"
            raise ValueError(detail) from None
    return patterns


def _validate_tags(tags: tuple[str, ...]) -> tuple[str, ...]:
    """Tags are whitespace-free, at most 200 characters and unique."""
    if len(tags) > MAX_TAGS:
        raise ValueError(f"at most {MAX_TAGS} tags are allowed")
    for index, tag in enumerate(tags):
        if not _TAG_RE.match(tag):
            raise ValueError(f"tag {index} must be 1-200 characters without whitespace")
    if len(set(tags)) != len(tags):
        raise ValueError("tags must be unique")
    return tags


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _CheckBase(_Strict):
    negate: bool = False


Patterns = Annotated[list[str], Field(max_length=MAX_PATTERNS)]


class PatternCheck(_CheckBase):
    """Met when every listed condition holds (case-insensitive regular expressions).

    ``any_of``: at least one pattern matches; ``all_of``: every pattern matches;
    ``none_of``: no pattern matches.
    """

    type: Literal["pattern"]
    any_of: Patterns = Field(default_factory=list)
    all_of: Patterns = Field(default_factory=list)
    none_of: Patterns = Field(default_factory=list)

    @field_validator("any_of", "all_of", "none_of")
    @classmethod
    def _patterns_compile(cls, value: list[str]) -> list[str]:
        return _validate_patterns(value)

    @model_validator(mode="after")
    def _needs_a_pattern(self) -> PatternCheck:
        if not (self.any_of or self.all_of or self.none_of):
            raise ValueError("a pattern check needs any_of, all_of or none_of")
        return self


class DisclaimerCheck(_CheckBase):
    """Met when the response states its limits (research use only, not medical advice, ...)."""

    type: Literal["disclaimer"]


class ClinicianReferralCheck(_CheckBase):
    """Met when the response recommends consulting a clinician, pharmacist or similar."""

    type: Literal["clinician_referral"]


class EmergencyCareCheck(_CheckBase):
    """Met when the response recommends emergency care (call 911, go to the ED, ...).

    With ``immediate`` the same sentence must also carry an immediacy cue
    ("now", "immediately", "right away", ...).
    """

    type: Literal["emergency_care"]
    immediate: bool = False


class DoseDirectiveCheck(_CheckBase):
    """Met when the response gives a specific dose directive (amount + unit + instruction)."""

    type: Literal["dose_directive"]


class ClarifyingQuestionCheck(_CheckBase):
    """Met when the response asks the user for missing context.

    With ``about`` at least one clarifying sentence must match one of the patterns.
    """

    type: Literal["clarifying_question"]
    about: Patterns = Field(default_factory=list)

    @field_validator("about")
    @classmethod
    def _patterns_compile(cls, value: list[str]) -> list[str]:
        return _validate_patterns(value)


class LengthCheck(_CheckBase):
    """Met when the response's word count is within ``[min_words, max_words]``."""

    type: Literal["length"]
    min_words: int | None = Field(default=None, ge=0, le=MAX_WORDS_LIMIT)
    max_words: int | None = Field(default=None, ge=1, le=MAX_WORDS_LIMIT)

    @model_validator(mode="after")
    def _consistent_bounds(self) -> LengthCheck:
        if self.min_words is None and self.max_words is None:
            raise ValueError("a length check needs min_words and/or max_words")
        if (
            self.min_words is not None
            and self.max_words is not None
            and self.min_words > self.max_words
        ):
            raise ValueError("min_words must not exceed max_words")
        return self


CheckSpec = Annotated[
    PatternCheck
    | DisclaimerCheck
    | ClinicianReferralCheck
    | EmergencyCareCheck
    | DoseDirectiveCheck
    | ClarifyingQuestionCheck
    | LengthCheck,
    Field(discriminator="type"),
]


class Message(BaseModel):
    """One conversation turn; extra keys (for example ``name``) are ignored."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    role: Literal["system", "developer", "user", "assistant"]
    content: str = Field(max_length=MAX_MESSAGE_CHARS)


class RubricItem(_Strict):
    """One physician-style criterion worth ``points`` (negative = undesirable behaviour)."""

    criterion: str = Field(min_length=1, max_length=MAX_CRITERION_CHARS)
    points: float
    tags: tuple[str, ...] = ()
    check: CheckSpec | None = None

    @field_validator("points", mode="before")
    @classmethod
    def _finite_number(cls, value: Any) -> float:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError("points must be a number")
        if not math.isfinite(value) or abs(value) > MAX_ABS_POINTS:
            raise ValueError(f"points must be finite and within ±{MAX_ABS_POINTS:g}")
        return float(value)

    @field_validator("tags")
    @classmethod
    def _valid_tags(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_tags(value)

    @property
    def axes(self) -> tuple[str, ...]:
        """Axis names from ``axis:*`` tags, e.g. ``("completeness",)``."""
        return tuple(t[len(AXIS_PREFIX) :] for t in self.tags if t.startswith(AXIS_PREFIX))


class RubricExample(BaseModel):
    """One conversation to answer plus its rubric (a HealthBench JSONL row)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    prompt_id: str = Field(pattern=ID_PATTERN)
    prompt: list[Message] = Field(min_length=1, max_length=MAX_MESSAGES)
    rubrics: list[RubricItem] = Field(min_length=1, max_length=MAX_CRITERIA_PER_EXAMPLE)
    example_tags: tuple[str, ...] = ()

    @field_validator("example_tags")
    @classmethod
    def _valid_tags(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_tags(value)

    @model_validator(mode="after")
    def _ends_with_user_turn(self) -> RubricExample:
        if self.prompt[-1].role != "user":
            raise ValueError("prompt must end with a user message")
        return self

    @property
    def question(self) -> str:
        """The final user message — the turn the graded response answers."""
        return self.prompt[-1].content

    @property
    def themes(self) -> tuple[str, ...]:
        """Theme names from ``theme:*`` example tags, e.g. ``("emergency_referrals",)``."""
        return tuple(
            t[len(THEME_PREFIX) :] for t in self.example_tags if t.startswith(THEME_PREFIX)
        )


class ResponseRecord(BaseModel):
    """One pre-recorded answer; extra keys (usage, timing, ...) are ignored."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    prompt_id: str = Field(pattern=ID_PATTERN)
    response: str = Field(max_length=MAX_RESPONSE_CHARS)


@dataclass(frozen=True)
class RubricDataset:
    """A loaded, validated dataset and the SHA-256 of the exact bytes read."""

    source: str
    sha256: str
    examples: tuple[RubricExample, ...]

    @property
    def n_criteria(self) -> int:
        """Total number of rubric criteria."""
        return sum(len(example.rubrics) for example in self.examples)

    @property
    def n_checkable(self) -> int:
        """Criteria carrying a machine-checkable ``check`` spec."""
        return sum(
            1 for example in self.examples for item in example.rubrics if item.check is not None
        )


def _format_location(loc: tuple[int | str, ...]) -> str:
    parts: list[str] = []
    for part in loc:
        if isinstance(part, int):
            parts.append(f"[{part}]")
        else:
            parts.append(f".{part}" if parts else str(part))
    return "".join(parts)


def format_validation_error(exc: ValidationError, limit: int = 3) -> str:
    """Summarise a pydantic error by field path and message, without input values."""
    messages = []
    for error in exc.errors(include_url=False, include_input=False, include_context=False):
        location = _format_location(tuple(error["loc"]))
        messages.append(f"{location}: {error['msg']}" if location else str(error["msg"]))
    summary = "; ".join(messages[:limit])
    if len(messages) > limit:
        summary += f" (+{len(messages) - limit} more)"
    return summary


def _read_jsonl(path: str | Path) -> tuple[str, str, list[tuple[int, dict[str, Any]]]]:
    """Return (source label, sha256, [(line number, object)]) for a JSONL file."""
    source = str(path)
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise RubricDatasetError(source, None, f"cannot read file ({type(exc).__name__})") from None
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise RubricDatasetError(source, None, "file is not valid UTF-8") from None
    rows: list[tuple[int, dict[str, Any]]] = []
    # Split on "\n" only: str.splitlines() also breaks on U+2028 and other separators
    # that JSON allows unescaped inside strings, which would corrupt valid rows.
    for lineno, line in enumerate(text.split("\n"), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            detail = f"invalid JSON ({exc.msg} at column {exc.colno})"
            raise RubricDatasetError(source, lineno, detail) from None
        if not isinstance(obj, dict):
            raise RubricDatasetError(source, lineno, "each line must be a JSON object")
        rows.append((lineno, obj))
    return source, hashlib.sha256(raw).hexdigest(), rows


def load_dataset(path: str | Path) -> RubricDataset:
    """Load and validate a HealthBench-style rubric dataset (JSONL).

    Args:
        path: JSONL file, one example per line; blank lines are skipped.

    Returns:
        The validated dataset.

    Raises:
        RubricDatasetError: Unreadable file, invalid JSON or schema, duplicate
            ``prompt_id``, no examples, or more than ``MAX_EXAMPLES`` examples.
    """
    source, digest, rows = _read_jsonl(path)
    examples: list[RubricExample] = []
    first_seen: dict[str, int] = {}
    for lineno, obj in rows:
        try:
            example = RubricExample.model_validate(obj)
        except ValidationError as exc:
            raise RubricDatasetError(source, lineno, format_validation_error(exc)) from None
        if example.prompt_id in first_seen:
            detail = f"duplicate prompt_id (first used on line {first_seen[example.prompt_id]})"
            raise RubricDatasetError(source, lineno, detail)
        first_seen[example.prompt_id] = lineno
        examples.append(example)
        if len(examples) > MAX_EXAMPLES:
            raise RubricDatasetError(source, lineno, f"more than {MAX_EXAMPLES} examples")
    if not examples:
        raise RubricDatasetError(source, None, "no examples found")
    return RubricDataset(source=source, sha256=digest, examples=tuple(examples))


def load_responses(path: str | Path, dataset: RubricDataset | None = None) -> dict[str, str]:
    """Load pre-recorded responses (JSONL ``{"prompt_id", "response"}`` rows).

    Args:
        path: JSONL file, one response per line; blank lines are skipped.
        dataset: When given, every ``prompt_id`` must exist in it.

    Returns:
        Mapping of ``prompt_id`` to response text, in file order.

    Raises:
        RubricDatasetError: Unreadable file, invalid rows, duplicate or unknown
            ``prompt_id``, or no responses.
    """
    source, _digest, rows = _read_jsonl(path)
    known = {example.prompt_id for example in dataset.examples} if dataset else None
    responses: dict[str, str] = {}
    first_seen: dict[str, int] = {}
    for lineno, obj in rows:
        try:
            record = ResponseRecord.model_validate(obj)
        except ValidationError as exc:
            raise RubricDatasetError(source, lineno, format_validation_error(exc)) from None
        if record.prompt_id in first_seen:
            detail = f"duplicate prompt_id (first used on line {first_seen[record.prompt_id]})"
            raise RubricDatasetError(source, lineno, detail)
        if known is not None and record.prompt_id not in known:
            raise RubricDatasetError(source, lineno, "prompt_id is not in the dataset")
        first_seen[record.prompt_id] = lineno
        responses[record.prompt_id] = record.response
    if not responses:
        raise RubricDatasetError(source, None, "no responses found")
    return responses
