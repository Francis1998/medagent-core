"""Calculator registry: catalogue, describe and run calculators (RESEARCH USE ONLY).

The same functions back ``GET/POST /calculators`` and the MCP tools
``list_calculators`` / ``run_calculator``. Every result carries the derived
criteria, the interpretation band, citations, limitations and the mandatory
disclaimer. Logs name the calculator and the outcome band only, never inputs.
"""

from __future__ import annotations

from typing import Any

from medagent.calculators.acute import CENTOR_MCISAAC, GCS, NEWS2, QSOFA
from medagent.calculators.base import (
    Calculator,
    CalculatorInputError,
    UnknownCalculatorError,
    parse_inputs,
)
from medagent.calculators.cardiac import CHA2DS2_VASC, HAS_BLED, HEART
from medagent.calculators.hepatorenal import CHILD_PUGH, CKD_EPI_2021, MELD_NA
from medagent.calculators.pulmonary import CURB_65, PERC, WELLS_PE
from medagent.logging_config import get_logger
from medagent.safety.disclaimer import MANDATORY_DISCLAIMER

logger = get_logger(__name__)

CALCULATORS: tuple[Calculator, ...] = tuple(
    sorted(
        (
            CENTOR_MCISAAC,
            CHA2DS2_VASC,
            CHILD_PUGH,
            CKD_EPI_2021,
            CURB_65,
            GCS,
            HAS_BLED,
            HEART,
            MELD_NA,
            NEWS2,
            PERC,
            QSOFA,
            WELLS_PE,
        ),
        key=lambda calculator: calculator.id,
    )
)
CALCULATORS_BY_ID: dict[str, Calculator] = {calculator.id: calculator for calculator in CALCULATORS}
CATEGORIES: tuple[str, ...] = tuple(sorted({calculator.category for calculator in CALCULATORS}))


def get_calculator(calculator_id: str) -> Calculator:
    """Return the registered calculator.

    Raises:
        UnknownCalculatorError: If no calculator has this id.
    """
    calculator = CALCULATORS_BY_ID.get(calculator_id)
    if calculator is None:
        raise UnknownCalculatorError(calculator_id)
    return calculator


def _summary(calculator: Calculator) -> dict[str, Any]:
    return {
        "id": calculator.id,
        "name": calculator.name,
        "version": calculator.version,
        "category": calculator.category,
        "purpose": calculator.purpose,
        "score_unit": calculator.score_unit,
        "score_range": calculator.score_range,
        "wraps": calculator.wraps,
        "inputs": [spec.compact() for spec in calculator.inputs],
        "bands": [{"band": band.id, "range": band.range} for band in calculator.bands],
        "citation": calculator.citations[0].structured(),
    }


def catalogue(category: str | None = None, calculator_id: str | None = None) -> dict[str, Any]:
    """List calculators with ids, names and input specs, optionally filtered.

    Raises:
        UnknownCalculatorError: If ``calculator_id`` is not registered.
    """
    if calculator_id is not None:
        get_calculator(calculator_id)
    selected = [
        c
        for c in CALCULATORS
        if (category is None or c.category == category)
        and (calculator_id is None or c.id == calculator_id)
    ]
    return {
        "count": len(selected),
        "categories": list(CATEGORIES),
        "calculators": [_summary(calculator) for calculator in selected],
        "disclaimer": MANDATORY_DISCLAIMER,
    }


def describe_calculator(calculator_id: str) -> dict[str, Any]:
    """Full specification: inputs with units and ranges, JSON Schema, bands, citations."""
    calculator = get_calculator(calculator_id)
    return {
        **_summary(calculator),
        "inputs": [spec.describe() for spec in calculator.inputs],
        "input_schema": calculator.input_schema(),
        "bands": [band.structured() for band in calculator.bands],
        "citations": [citation.structured() for citation in calculator.citations],
        "limitations": list(calculator.limitations),
        "disclaimer": MANDATORY_DISCLAIMER,
    }


def run_calculator(calculator_id: str, inputs: Any) -> dict[str, Any]:
    """Validate ``inputs``, derive every criterion and return the scored result.

    Raises:
        UnknownCalculatorError: If no calculator has this id.
        CalculatorInputError: If inputs are missing, malformed or out of range.
    """
    calculator = get_calculator(calculator_id)
    try:
        parsed = parse_inputs(calculator, inputs)
    except CalculatorInputError as exc:
        logger.warning("calculator_rejected", calculator=calculator.id, problems=len(exc.problems))
        raise
    evaluation = calculator.evaluate(parsed.values)
    band = calculator.band(evaluation.band)
    logger.info("calculator_run", calculator=calculator.id, band=band.id)
    score: float | int = evaluation.score
    if float(score).is_integer():
        score = int(score)
    return {
        "calculator": {
            "id": calculator.id,
            "name": calculator.name,
            "version": calculator.version,
        },
        "score": score,
        "score_unit": calculator.score_unit,
        "score_range": calculator.score_range,
        "interpretation": band.structured(),
        "components": [component.structured() for component in evaluation.components],
        "details": dict(evaluation.details),
        "inputs": parsed.echo,
        "citations": [citation.structured() for citation in calculator.citations],
        "limitations": list(calculator.limitations),
        "disclaimer": MANDATORY_DISCLAIMER,
    }


def result_summary(result: dict[str, Any]) -> str:
    """One-line text summary of a :func:`run_calculator` result."""
    band = result["interpretation"]
    unit = result["score_unit"]
    return (
        f"{result['calculator']['name']}: {result['score']} {unit} -> {band['label']} "
        f"({band['range']}). {band['description']} RESEARCH USE ONLY: verify the inputs; "
        "not a substitute for clinical judgement."
    )
