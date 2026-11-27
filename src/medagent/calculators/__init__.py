"""Validated clinical calculators as deterministic tools (RESEARCH USE ONLY).

Each calculator takes raw patient values with units, derives every criterion
transparently and returns the score, its components, the interpretation band,
citations, limitations and the mandatory disclaimer. Exposed through
``/calculators`` (HTTP) and the MCP tools ``list_calculators`` /
``run_calculator``; never a treatment recommendation.
"""

from medagent.calculators.base import Calculator, CalculatorInputError, UnknownCalculatorError
from medagent.calculators.registry import (
    CALCULATORS,
    CALCULATORS_BY_ID,
    CATEGORIES,
    catalogue,
    describe_calculator,
    get_calculator,
    result_summary,
    run_calculator,
)

__all__ = [
    "CALCULATORS",
    "CALCULATORS_BY_ID",
    "CATEGORIES",
    "Calculator",
    "CalculatorInputError",
    "UnknownCalculatorError",
    "catalogue",
    "describe_calculator",
    "get_calculator",
    "result_summary",
    "run_calculator",
]
