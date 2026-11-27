"""Shared input specifications and unit conversions for the calculator registry."""

from __future__ import annotations

from medagent.calculators.base import Choice, InputSpec, Unit

FAHRENHEIT = Unit(
    "°F",
    factor=5 / 9,
    offset=-160 / 9,
    aliases=("F", "degF", "[degF]"),
    formula="°C = (°F - 32) x 5/9",
)
CREATININE_UMOL = Unit(
    "µmol/L", factor=1 / 88.4, aliases=("umol/L",), formula="mg/dL = µmol/L / 88.4"
)
BILIRUBIN_UMOL = Unit(
    "µmol/L", factor=1 / 17.1, aliases=("umol/L",), formula="mg/dL = µmol/L / 17.1"
)
ALBUMIN_G_L = Unit("g/L", factor=0.1, formula="g/dL = g/L / 10")
BUN_MG_DL = Unit(
    "mg/dL",
    factor=0.357,
    aliases=("mg/dL BUN",),
    note="blood urea nitrogen (BUN) as reported by US laboratories",
    formula="urea mmol/L = BUN mg/dL x 0.357",
)
SODIUM_MEQ = Unit("mEq/L", aliases=("meq/L",))


def age(minimum: int = 18, *, description: str = "Age in completed years.") -> InputSpec:
    return InputSpec(
        "age", "Age", "integer", description, unit="years", minimum=minimum, maximum=120
    )


def sex() -> InputSpec:
    return InputSpec(
        "sex",
        "Sex",
        "choice",
        "Sex as used by the published equation or score.",
        choices=(Choice("female", "Female"), Choice("male", "Male")),
    )


def heart_rate(description: str = "Heart rate (pulse).") -> InputSpec:
    return InputSpec(
        "heart_rate",
        "Heart rate",
        "integer",
        description,
        unit="beats/min",
        minimum=20,
        maximum=300,
    )


def respiratory_rate() -> InputSpec:
    return InputSpec(
        "respiratory_rate",
        "Respiratory rate",
        "integer",
        "Respiratory rate.",
        unit="breaths/min",
        minimum=0,
        maximum=80,
    )


def systolic_bp() -> InputSpec:
    return InputSpec(
        "systolic_bp",
        "Systolic blood pressure",
        "integer",
        "Systolic blood pressure.",
        unit="mmHg",
        minimum=30,
        maximum=300,
    )


def oxygen_saturation(description: str = "Peripheral oxygen saturation (SpO2).") -> InputSpec:
    return InputSpec(
        "oxygen_saturation", "SpO2", "integer", description, unit="%", minimum=50, maximum=100
    )


def temperature(description: str = "Body temperature.") -> InputSpec:
    return InputSpec(
        "temperature",
        "Temperature",
        "number",
        description,
        unit="°C",
        unit_aliases=("C", "degC", "Cel"),
        alternative_units=(FAHRENHEIT,),
        minimum=25,
        maximum=45,
    )


def creatinine() -> InputSpec:
    return InputSpec(
        "creatinine",
        "Serum creatinine",
        "number",
        "Serum creatinine (IDMS-traceable assay).",
        unit="mg/dL",
        alternative_units=(CREATININE_UMOL,),
        minimum=0.1,
        maximum=25,
    )


def bilirubin() -> InputSpec:
    return InputSpec(
        "bilirubin",
        "Total bilirubin",
        "number",
        "Serum total bilirubin.",
        unit="mg/dL",
        alternative_units=(BILIRUBIN_UMOL,),
        minimum=0.1,
        maximum=80,
    )


def inr() -> InputSpec:
    return InputSpec(
        "inr", "INR", "number", "International normalised ratio.", minimum=0.5, maximum=20
    )


def boolean(name: str, label: str, description: str) -> InputSpec:
    return InputSpec(name, label, "boolean", description)
