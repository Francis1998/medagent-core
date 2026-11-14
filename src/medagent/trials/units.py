"""Unit handling for lab criteria: exact conversions within one dimension only.

eGFR units reuse the MCP layer's recognised spellings and factors
(``medagent.mcp.tools._egfr_unit_factor``: mL/min/1.73m² and mL/s/1.73m²). Other
units convert only within one dimension (mass concentration, substance
concentration, cell counts, catalytic activity, ...), with exact decimal factors
and never across dimensions: mg/dL cannot become µmol/L without an
analyte-specific molar mass, so such a comparison is reported as
``insufficient_data`` instead of being guessed. RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from decimal import Decimal

from medagent.mcp.tools import _egfr_unit_factor

_GFR = "glomerular_filtration_rate"
_RATIO = "ratio"

# Normalised unit spelling -> (dimension, factor to the dimension's base unit).
_UNITS: dict[str, tuple[str, Decimal]] = {
    # Mass concentration (base g/L).
    "g/l": ("mass_concentration", Decimal("1")),
    "g/dl": ("mass_concentration", Decimal("10")),
    "mg/ml": ("mass_concentration", Decimal("1")),
    "mg/dl": ("mass_concentration", Decimal("0.01")),
    "mg/l": ("mass_concentration", Decimal("0.001")),
    "ug/ml": ("mass_concentration", Decimal("0.001")),
    "ug/dl": ("mass_concentration", Decimal("0.00001")),
    "ug/l": ("mass_concentration", Decimal("0.000001")),
    "ng/ml": ("mass_concentration", Decimal("0.000001")),
    "ng/dl": ("mass_concentration", Decimal("0.00000001")),
    "ng/l": ("mass_concentration", Decimal("0.000000001")),
    "pg/ml": ("mass_concentration", Decimal("0.000000001")),
    # Substance concentration (base mmol/L).
    "mol/l": ("substance_concentration", Decimal("1000")),
    "mmol/l": ("substance_concentration", Decimal("1")),
    "umol/l": ("substance_concentration", Decimal("0.001")),
    "nmol/l": ("substance_concentration", Decimal("0.000001")),
    "pmol/l": ("substance_concentration", Decimal("0.000000001")),
    # Equivalents are kept apart: mEq/L equals mmol/L only for monovalent ions.
    "meq/l": ("equivalent_concentration", Decimal("1")),
    # Cell counts per volume (base 10^9/L = 10^3/µL).
    "10*9/l": ("number_concentration", Decimal("1")),
    "10e9/l": ("number_concentration", Decimal("1")),
    "10*3/ul": ("number_concentration", Decimal("1")),
    "10e3/ul": ("number_concentration", Decimal("1")),
    "10*3/mm3": ("number_concentration", Decimal("1")),
    "k/ul": ("number_concentration", Decimal("1")),
    "thou/ul": ("number_concentration", Decimal("1")),
    "/nl": ("number_concentration", Decimal("1")),
    "10*6/ul": ("number_concentration", Decimal("1000")),
    "10*12/l": ("number_concentration", Decimal("1000")),
    "10*6/l": ("number_concentration", Decimal("0.001")),
    "/ul": ("number_concentration", Decimal("0.001")),
    "cells/ul": ("number_concentration", Decimal("0.001")),
    "/mm3": ("number_concentration", Decimal("0.001")),
    "cells/mm3": ("number_concentration", Decimal("0.001")),
    # Catalytic activity concentration (base U/L; 1 µkat/L = 60 U/L).
    "u/l": ("catalytic_concentration", Decimal("1")),
    "iu/l": ("catalytic_concentration", Decimal("1")),
    "[iu]/l": ("catalytic_concentration", Decimal("1")),
    "ukat/l": ("catalytic_concentration", Decimal("60")),
    "nkat/l": ("catalytic_concentration", Decimal("0.06")),
    # Percentages (HbA1c NGSP %, ejection fraction, ...).
    "%": ("percent", Decimal("1")),
    # Dimensionless ratios such as the INR.
    "1": (_RATIO, Decimal("1")),
    "{ratio}": (_RATIO, Decimal("1")),
    "ratio": (_RATIO, Decimal("1")),
    "{inr}": (_RATIO, Decimal("1")),
    "inr": (_RATIO, Decimal("1")),
    # Time (base seconds), e.g. prothrombin time.
    "s": ("time", Decimal("1")),
    "sec": ("time", Decimal("1")),
    "min": ("time", Decimal("60")),
    "h": ("time", Decimal("3600")),
    # Pressure, body-mass index and clearances that are not BSA-normalised.
    "mm[hg]": ("pressure", Decimal("1")),
    "mmhg": ("pressure", Decimal("1")),
    "kg/m2": ("body_mass_index", Decimal("1")),
    "ml/min": ("volume_rate", Decimal("1")),
    "ml/s": ("volume_rate", Decimal("60")),
}


def _normalise(unit: str) -> str:
    """Lower-case a unit and unify spacing, micro signs, superscripts and exponents."""
    key = re.sub(r"\s+", "", unit.lower())
    key = key.replace("µ", "u").replace("μ", "u").replace("²", "2").replace("³", "3")
    key = key.replace("×", "x").replace("^", "*")
    return key[1:] if key.startswith("x10*") else key


def _dimension(unit: str) -> tuple[str, Decimal] | None:
    """Return (dimension, factor to its base unit) for a supported unit spelling."""
    gfr_factor = _egfr_unit_factor(unit)
    if gfr_factor is not None:
        return _GFR, Decimal(str(gfr_factor))
    return _UNITS.get(_normalise(unit))


def is_supported_unit(unit: str) -> bool:
    """True when ``unit`` is a spelling this module can convert."""
    return _dimension(unit) is not None


def same_unit(first: str, second: str) -> bool:
    """True when two spellings denote the same supported unit (e.g. UCUM code and display)."""
    dimension = _dimension(first)
    return dimension is not None and dimension == _dimension(second)


def convert(value: Decimal, from_unit: str | None, to_unit: str) -> Decimal | None:
    """Express ``value`` (recorded in ``from_unit``) in ``to_unit``.

    The value is multiplied by the source factor before dividing by the target
    factor, so conversions such as 30 mL/min -> 0.5 mL/s stay exact.

    Args:
        value: Recorded value.
        from_unit: Unit recorded with the observation (None when it has none).
        to_unit: Unit of the criterion threshold.

    Returns:
        The converted value, or None when either unit is unknown or the units
        belong to different dimensions. A value without a unit is accepted only
        for a dimensionless criterion unit (a ratio such as the INR).
    """
    target = _dimension(to_unit)
    if target is None:
        return None
    if from_unit is None or not from_unit.strip():
        return value if target[0] == _RATIO else None
    source = _dimension(from_unit)
    if source is None or source[0] != target[0]:
        return None
    return value * source[1] / target[1]
