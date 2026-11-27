"""MeldNaScorer (research-only clinical score).

Advisory scorer closing the MDCalc / AASLD / EHR MELD-Na score gap for
offline medical-ward agent pipelines.
Distinct from ``ChildPughLiverSeverityScorer / SofaOrganFailureScorer``. Prefer
GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro for narrative summaries.
Never modifies medications and never performs network I/O.

Computes the OPTN MELD-Na (Kim et al., N Engl J Med 2008;359:1018, PMID
18768945; OPTN policy 2016) from raw labs and bands it with the Wiesner et al.
3-month mortality strata (Gastroenterology 2003;124:91, PMID 12512033):
< 10 low, 10-19 intermediate, >= 20 high. Legacy callers that pass only the
0/1 threshold flags get the lowest MELD-Na consistent with those flags.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from medagent.logging_config import get_logger
from medagent.models import MeldNaRisk, Severity

logger = get_logger(__name__)

MELD_NA_MAX = 40
_LAB_FIELDS = ("bilirubin_mg_dl", "inr", "creatinine_mg_dl", "sodium_mmol_l")
_FLAG_FIELDS = ("bilirubin_ge_2", "inr_ge_1_5", "creatinine_ge_1_5", "sodium_lt_135")


@dataclass(frozen=True, slots=True)
class MeldNaFactors:
    """MeldNaScorer inputs.

    Supply all four raw labs for the exact OPTN MELD-Na. The 0/1 threshold
    flags are kept for backward compatibility: flags alone only bound the score
    from below (each set flag pins its lab at the threshold, each unset flag at
    the MELD floor), so the result is the lowest MELD-Na consistent with them.
    ``dialysis`` (>= 2 dialyses or >= 24 h of CVVHD in the past week) applies to
    both forms and sets creatinine to 4.0 mg/dL.
    """

    bilirubin_ge_2: int = 0
    inr_ge_1_5: int = 0
    creatinine_ge_1_5: int = 0
    sodium_lt_135: int = 0
    dialysis: int = 0
    bilirubin_mg_dl: float | None = None
    inr: float | None = None
    creatinine_mg_dl: float | None = None
    sodium_mmol_l: float | None = None


@dataclass(frozen=True, slots=True)
class MeldNaComputation:
    """OPTN MELD-Na with the bounded lab values that entered the formula."""

    meld: int
    meld_na: int
    bilirubin_mg_dl: float
    inr: float
    creatinine_mg_dl: float
    sodium_mmol_l: float


def _round_half_up(value: float, places: str = "1") -> Decimal:
    return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def compute_meld_na(
    *,
    bilirubin_mg_dl: float,
    inr: float,
    creatinine_mg_dl: float,
    sodium_mmol_l: float,
    dialysis: bool,
) -> MeldNaComputation:
    """Return the OPTN MELD-Na (2016 policy) for raw labs.

    Labs below 1.0 are set to 1.0, creatinine is capped at 4.0 mg/dL (and set
    to 4.0 with dialysis), sodium is bounded to 125-137 mmol/L. MELD(i) is
    rounded to the tenth and multiplied by 10; the sodium term applies only when
    MELD(i) > 11; the result is capped at 40.

    Raises:
        ValueError: If a lab is not a positive finite number.
    """
    labs = {
        "bilirubin_mg_dl": bilirubin_mg_dl,
        "inr": inr,
        "creatinine_mg_dl": creatinine_mg_dl,
        "sodium_mmol_l": sodium_mmol_l,
    }
    for name, value in labs.items():
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be a positive number")
    bilirubin = max(bilirubin_mg_dl, 1.0)
    bounded_inr = max(inr, 1.0)
    creatinine = 4.0 if dialysis else min(max(creatinine_mg_dl, 1.0), 4.0)
    sodium = min(max(sodium_mmol_l, 125.0), 137.0)
    meld_i = (
        0.957 * math.log(creatinine)
        + 0.378 * math.log(bilirubin)
        + 1.120 * math.log(bounded_inr)
        + 0.643
    )
    meld = int(_round_half_up(float(_round_half_up(meld_i, "0.1")) * 10))
    if meld > 11:
        adjusted = meld + 1.32 * (137 - sodium) - 0.033 * meld * (137 - sodium)
        meld_na = int(_round_half_up(adjusted))
    else:
        meld_na = meld
    return MeldNaComputation(
        meld=min(meld, MELD_NA_MAX),
        meld_na=min(meld_na, MELD_NA_MAX),
        bilirubin_mg_dl=bilirubin,
        inr=bounded_inr,
        creatinine_mg_dl=creatinine,
        sodium_mmol_l=sodium,
    )


def meld_na_band(meld_na: int) -> tuple[str, Severity]:
    """Band a MELD-Na with the Wiesner 2003 strata (< 10, 10-19, >= 20)."""
    if meld_na >= 20:
        return "high", Severity.HIGH
    if meld_na >= 10:
        return "intermediate", Severity.MODERATE
    return "low", Severity.LOW


class MeldNaScorer:
    """Compute advisory MeldNaRisk findings."""

    def check(self, factors: MeldNaFactors) -> list[MeldNaRisk]:
        """Return one advisory finding with the MELD-Na and its band.

        Raises:
            ValueError: If a flag is not 0/1, the raw labs are incomplete or
                mixed with threshold flags, or a lab is not positive.
        """
        binaries = {name: getattr(factors, name) for name in (*_FLAG_FIELDS, "dialysis")}
        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")
        labs = {name: getattr(factors, name) for name in _LAB_FIELDS}
        supplied = [name for name, value in labs.items() if value is not None]
        if supplied and len(supplied) != len(_LAB_FIELDS):
            raise ValueError(
                "bilirubin_mg_dl, inr, creatinine_mg_dl and sodium_mmol_l must be supplied together"
            )
        exact = bool(supplied)
        if exact and any(binaries[name] for name in _FLAG_FIELDS):
            raise ValueError("pass either the raw labs or the threshold flags, not both")
        dialysis = bool(factors.dialysis)
        if exact:
            result = compute_meld_na(
                bilirubin_mg_dl=float(labs["bilirubin_mg_dl"]),
                inr=float(labs["inr"]),
                creatinine_mg_dl=float(labs["creatinine_mg_dl"]),
                sodium_mmol_l=float(labs["sodium_mmol_l"]),
                dialysis=dialysis,
            )
            positive = [
                name
                for name, abnormal in (
                    ("bilirubin_ge_2", float(labs["bilirubin_mg_dl"]) >= 2.0),
                    ("inr_ge_1_5", float(labs["inr"]) >= 1.5),
                    ("creatinine_ge_1_5", float(labs["creatinine_mg_dl"]) >= 1.5),
                    ("sodium_lt_135", float(labs["sodium_mmol_l"]) < 135.0),
                    ("dialysis", dialysis),
                )
                if abnormal
            ]
        else:
            result = compute_meld_na(
                bilirubin_mg_dl=2.0 if factors.bilirubin_ge_2 else 1.0,
                inr=1.5 if factors.inr_ge_1_5 else 1.0,
                creatinine_mg_dl=1.5 if factors.creatinine_ge_1_5 else 1.0,
                sodium_mmol_l=135.0 if factors.sodium_lt_135 else 137.0,
                dialysis=dialysis,
            )
            positive = [name for name, value in binaries.items() if value > 0]
        score = result.meld_na
        band, severity = meld_na_band(score)
        basis = (
            "raw labs"
            if exact
            else "threshold flags only (lower bound; supply the raw labs for the exact score)"
        )
        rationale = (
            "RESEARCH USE ONLY: MeldNaScorer MELD-Na "
            f"{score} ({band}) from {basis}; abnormal factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = MeldNaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("meld_na_scorer_scored", score=score, band=band)
        return [finding]
