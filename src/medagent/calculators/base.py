"""Typed building blocks of the clinical calculator registry (RESEARCH USE ONLY).

A :class:`Calculator` declares its inputs (:class:`InputSpec`: type, canonical
unit, accepted alternative units with their conversions, physiological range,
required or optional), its interpretation bands, citations and limitations,
and an ``evaluate`` function that derives every criterion from the normalised
raw values. :func:`parse_inputs` validates and converts caller values; problems
are collected into one :class:`CalculatorInputError` whose messages name the
input but never echo the value.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from medagent.models import Severity

INPUT_KINDS = ("number", "integer", "boolean", "choice")


class CalculatorInputError(ValueError):
    """Missing, malformed or out-of-range calculator inputs (HTTP 422 / MCP ``isError``)."""

    def __init__(self, calculator_id: str, problems: list[str]) -> None:
        self.calculator_id = calculator_id
        self.problems = problems
        super().__init__(f"Invalid inputs for {calculator_id}: " + "; ".join(problems))


class UnknownCalculatorError(KeyError):
    """No calculator is registered under the requested id (HTTP 404)."""

    def __str__(self) -> str:
        return "Unknown calculator id; list_calculators / GET /calculators lists the ids."


def _unit_key(symbol: str) -> str:
    """Normalise a unit spelling: case, spaces and the micro sign do not matter."""
    return symbol.replace("µ", "u").replace("μ", "u").replace(" ", "").lower()


@dataclass(frozen=True)
class Unit:
    """An accepted unit: ``canonical = value * factor + offset``."""

    symbol: str
    factor: float = 1.0
    offset: float = 0.0
    aliases: tuple[str, ...] = ()
    note: str = ""
    formula: str = ""

    def keys(self) -> set[str]:
        return {_unit_key(self.symbol), *(_unit_key(alias) for alias in self.aliases)}

    def to_canonical(self, value: float) -> float:
        # Rounding removes float noise such as 100.4 degF -> 38.000000000000007 degC,
        # which would otherwise cross a "> 38.0" threshold.
        return round(value * self.factor + self.offset, 6)

    @property
    def is_identity(self) -> bool:
        return self.factor == 1.0 and self.offset == 0.0


@dataclass(frozen=True)
class Choice:
    """One allowed value of a ``choice`` input."""

    value: str
    label: str


@dataclass(frozen=True)
class InputSpec:
    """One calculator input: type, canonical unit, alternatives, range and requiredness."""

    name: str
    label: str
    kind: str
    description: str
    unit: str | None = None
    unit_aliases: tuple[str, ...] = ()
    alternative_units: tuple[Unit, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[Choice, ...] = ()
    required: bool = True
    default: Any = None

    def __post_init__(self) -> None:
        if self.kind not in INPUT_KINDS:
            raise ValueError(f"unknown input kind {self.kind!r}")

    @property
    def units(self) -> tuple[Unit, ...]:
        if self.unit is None:
            return ()
        return (Unit(self.unit, aliases=self.unit_aliases), *self.alternative_units)

    @property
    def requires_explicit_unit(self) -> bool:
        """True when a bare number would be ambiguous (some unit changes the number)."""
        return any(not unit.is_identity for unit in self.alternative_units)

    def range_text(self) -> str:
        low, high = fmt_number(self.minimum), fmt_number(self.maximum)
        return f"{low} and {high} {self.unit or ''}".rstrip()

    def describe(self) -> dict[str, Any]:
        """JSON-ready description used by ``GET /calculators`` and ``list_calculators``."""
        spec: dict[str, Any] = {
            "name": self.name,
            "label": self.label,
            "type": self.kind,
            "required": self.required,
            "description": self.description,
        }
        if self.unit is not None:
            spec["unit"] = self.unit
            spec["accepted_units"] = [
                {
                    "unit": unit.symbol,
                    "to_canonical": _conversion_text(unit, self.unit),
                    **({"note": unit.note} if unit.note else {}),
                }
                for unit in self.units
            ]
            spec["unit_required"] = self.requires_explicit_unit
        if self.minimum is not None or self.maximum is not None:
            spec["range"] = {"minimum": self.minimum, "maximum": self.maximum, "unit": self.unit}
        if self.choices:
            spec["choices"] = [{"value": c.value, "label": c.label} for c in self.choices]
        if not self.required:
            spec["default"] = self.default
        return spec

    def compact(self) -> dict[str, Any]:
        """Fixed-shape input summary used by the catalogue listing."""
        return {
            "name": self.name,
            "type": self.kind,
            "required": self.required,
            "unit": self.unit,
            "accepted_units": [unit.symbol for unit in self.units],
            "unit_required": self.requires_explicit_unit,
            "choices": [choice.value for choice in self.choices],
            "minimum": self.minimum,
            "maximum": self.maximum,
            "default": self.default,
            "description": self.description,
        }

    def json_schema(self) -> dict[str, Any]:
        """JSON Schema (2020-12 subset) fragment for this input."""
        if self.kind == "boolean":
            return {"type": "boolean", "description": self.description}
        if self.kind == "choice":
            return {
                "type": "string",
                "enum": [choice.value for choice in self.choices],
                "description": self.description,
            }
        number: dict[str, Any] = {"type": self.kind}
        quantity: dict[str, Any] = {
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "unit": {"type": "string", "enum": [unit.symbol for unit in self.units]},
            },
            "required": ["value", "unit"],
            "additionalProperties": False,
        }
        if self.unit is None:
            return {**number, "description": self.description}
        if self.requires_explicit_unit:
            return {**quantity, "description": self.description}
        return {"anyOf": [number, quantity], "description": self.description}


def fmt_number(value: float | None) -> str:
    """Format a number without float noise: 7 -> '7', 9.2820 -> '9.28'."""
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _conversion_text(unit: Unit, canonical: str) -> str:
    if unit.is_identity:
        return "identity"
    if unit.formula:
        return unit.formula
    text = f"{canonical} = {unit.symbol} x {unit.factor:g}"
    if unit.offset:
        text += f" {'+' if unit.offset > 0 else '-'} {abs(unit.offset):g}"
    return text


@dataclass(frozen=True)
class Criterion:
    """One derived criterion in a result: the points it contributed and the rule that fired.

    Formula-based calculators (MELD-Na, CKD-EPI) set ``points`` to ``None`` and report the
    term or factor the criterion contributed as ``value``.
    """

    criterion: str
    label: str
    points: float | None
    rule: str
    inputs: tuple[str, ...]
    value: float | None = None

    @property
    def earned(self) -> float:
        """Points contributed to a points-based total (0 for formula terms)."""
        return self.points or 0

    def structured(self) -> dict[str, Any]:
        points: float | int | None = self.points
        if points is not None and float(points).is_integer():
            points = int(points)
        structured: dict[str, Any] = {
            "criterion": self.criterion,
            "label": self.label,
            "points": points,
            "rule": self.rule,
            "inputs": list(self.inputs),
        }
        if self.value is not None:
            structured["value"] = self.value
        return structured


@dataclass(frozen=True)
class Band:
    """A published interpretation band (risk description, never a treatment instruction)."""

    id: str
    label: str
    range: str
    description: str
    severity: Severity

    def structured(self) -> dict[str, Any]:
        return {
            "band": self.id,
            "label": self.label,
            "range": self.range,
            "description": self.description,
            "severity": self.severity.value,
        }


@dataclass(frozen=True)
class Citation:
    """Primary source for the formula, cut-offs or bands."""

    reference: str
    doi: str | None = None
    pmid: str | None = None
    url: str | None = None

    def structured(self) -> dict[str, Any]:
        return {"reference": self.reference, "doi": self.doi, "pmid": self.pmid, "url": self.url}


@dataclass(frozen=True)
class Evaluation:
    """Outcome of one calculator evaluation, before it is rendered."""

    score: float
    components: tuple[Criterion, ...]
    band: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Calculator:
    """A registered calculator: metadata, input specs, bands and the evaluation function."""

    id: str
    name: str
    version: str
    category: str
    purpose: str
    inputs: tuple[InputSpec, ...]
    bands: tuple[Band, ...]
    citations: tuple[Citation, ...]
    limitations: tuple[str, ...]
    evaluate: Callable[[Mapping[str, Any]], Evaluation]
    score_unit: str = "points"
    score_range: str = ""
    wraps: str | None = None

    def band(self, band_id: str) -> Band:
        for band in self.bands:
            if band.id == band_id:
                return band
        raise LookupError(f"{self.id} has no band {band_id!r}")

    def input_schema(self) -> dict[str, Any]:
        """JSON Schema for this calculator's ``inputs`` object."""
        return {
            "type": "object",
            "properties": {spec.name: spec.json_schema() for spec in self.inputs},
            "required": [spec.name for spec in self.inputs if spec.required],
            "additionalProperties": False,
        }


@dataclass(frozen=True)
class ParsedInputs:
    """Validated inputs in canonical units plus the JSON echo returned to the caller."""

    values: dict[str, Any]
    echo: dict[str, Any]


def _finite_float(value: Any) -> float | None:
    """``value`` as a finite float, or ``None`` for non-numbers, NaN, infinities and
    integers too large for a float (JSON allows arbitrarily long integers)."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) else None


def _parse_quantity(spec: InputSpec, raw: Any, path: str) -> tuple[float, dict[str, Any]] | str:
    """Return (canonical value, echo) or a problem message for a numeric input."""
    reported: dict[str, Any] | None = None
    if isinstance(raw, dict):
        if spec.unit is None or set(raw) != {"value", "unit"}:
            return f"{path} must be a number" + (
                ' or {"value": <number>, "unit": "<unit>"}' if spec.unit else ""
            )
        value, unit_text = raw["value"], raw["unit"]
        if not isinstance(unit_text, str):
            return f"{path}.unit must be a string"
        unit = next((u for u in spec.units if _unit_key(unit_text) in u.keys()), None)
        if unit is None:
            accepted = ", ".join(u.symbol for u in spec.units)
            return f"{path}.unit must be one of {accepted}"
        number = _finite_float(value)
        if number is None:
            return f"{path}.value must be a finite number"
        canonical = unit.to_canonical(number)
        if not unit.is_identity:
            reported = {"value": value, "unit": unit.symbol}
    else:
        number = _finite_float(raw)
        if number is None:
            return f"{path} must be a finite number"
        if spec.requires_explicit_unit:
            accepted = " | ".join(f'"{u.symbol}"' for u in spec.units)
            return f'{path} needs an explicit unit: {{"value": <number>, "unit": {accepted}}}'
        canonical = number
    if spec.kind == "integer":
        if not canonical.is_integer():
            return f"{path} must be a whole number"
        canonical = int(canonical)
    if (spec.minimum is not None and canonical < spec.minimum) or (
        spec.maximum is not None and canonical > spec.maximum
    ):
        return f"{path} must be between {spec.range_text()}"
    echo: dict[str, Any] = {"value": canonical, "unit": spec.unit}
    if reported is not None:
        echo["reported"] = reported
    return canonical, echo


def parse_inputs(calculator: Calculator, raw_inputs: Any) -> ParsedInputs:
    """Validate ``raw_inputs`` against ``calculator.inputs`` and convert to canonical units.

    Raises:
        CalculatorInputError: Listing every problem; values are never echoed.
    """
    if not isinstance(raw_inputs, dict):
        raise CalculatorInputError(calculator.id, ["inputs must be an object"])
    problems: list[str] = []
    allowed = {spec.name for spec in calculator.inputs}
    if any(name not in allowed for name in raw_inputs):
        # Unknown names are caller-controlled text, so they are never echoed back.
        problems.append(f"inputs has unexpected properties (allowed: {', '.join(sorted(allowed))})")
    values: dict[str, Any] = {}
    echo: dict[str, Any] = {}
    for spec in calculator.inputs:
        path = f"inputs.{spec.name}"
        if spec.name not in raw_inputs:
            if spec.required:
                problems.append(f"{path} is required")
            else:
                values[spec.name] = spec.default
                echo[spec.name] = {"value": spec.default, "defaulted": True}
            continue
        raw = raw_inputs[spec.name]
        if spec.kind == "boolean":
            if not isinstance(raw, bool):
                problems.append(f"{path} must be true or false")
                continue
            values[spec.name] = raw
            echo[spec.name] = {"value": raw}
        elif spec.kind == "choice":
            allowed_values = [choice.value for choice in spec.choices]
            if not isinstance(raw, str) or raw not in allowed_values:
                problems.append(f"{path} must be one of {', '.join(allowed_values)}")
                continue
            values[spec.name] = raw
            echo[spec.name] = {"value": raw}
        else:
            parsed = _parse_quantity(spec, raw, path)
            if isinstance(parsed, str):
                problems.append(parsed)
                continue
            values[spec.name], echo[spec.name] = parsed
    if problems:
        raise CalculatorInputError(calculator.id, problems)
    return ParsedInputs(values, echo)


# ---------------------------------------------------------------------------
# Criterion helpers shared by the calculator definitions
# ---------------------------------------------------------------------------


def flag(criterion: str, label: str, present: bool, points: float, input_name: str) -> Criterion:
    """A yes/no criterion taken directly from a boolean input."""
    rule = f"{input_name} {'true' if present else 'false'}: {_signed(points if present else 0)}"
    return Criterion(criterion, label, points if present else 0, rule, (input_name,))


def threshold(
    criterion: str,
    label: str,
    *,
    input_name: str,
    value: float,
    unit: str,
    met: bool,
    met_text: str,
    unmet_text: str,
    points: float,
) -> Criterion:
    """A criterion that fires when ``value`` crosses one published cut-off."""
    shown = f"{input_name} {fmt_number(value)} {unit}".rstrip()
    rule = f"{shown} {met_text if met else unmet_text}: {_signed(points if met else 0)}"
    return Criterion(criterion, label, points if met else 0, rule, (input_name,))


def _signed(points: float) -> str:
    return f"+{fmt_number(points)}" if points > 0 else fmt_number(points)


def checked_total(calculator_id: str, total: float, components: tuple[Criterion, ...]) -> float:
    """Return the wrapped scorer's ``total`` after checking it equals the derived points."""
    if not math.isclose(sum(c.earned for c in components), total):
        raise RuntimeError(f"{calculator_id}: scorer total disagrees with the derived criteria")
    return total


def points_for(value: float, bands: tuple[tuple[float, float], ...]) -> float:
    """Points of the first ``(upper_inclusive, points)`` band containing ``value``."""
    for upper, points in bands:
        if value <= upper:
            return points
    raise ValueError("value above every band")


def banded(
    criterion: str,
    label: str,
    *,
    input_name: str,
    value: float,
    unit: str,
    table: tuple[tuple[float, int, str], ...],
) -> Criterion:
    """A multi-level criterion: the first ``(upper_inclusive, points, text)`` row that fits."""
    for upper, points, text in table:
        if value <= upper:
            shown = f"{input_name} {fmt_number(value)} {unit}".rstrip()
            return Criterion(
                criterion, label, points, f"{shown} in {text}: {_signed(points)}", (input_name,)
            )
    raise ValueError(f"{input_name} is above every band")
