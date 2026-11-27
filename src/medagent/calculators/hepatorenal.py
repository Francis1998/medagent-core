"""MELD-Na, Child-Pugh and CKD-EPI 2021 calculators."""

from __future__ import annotations

import math
from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from medagent.calculators import inputs as common
from medagent.calculators.base import (
    Band,
    Calculator,
    Choice,
    Citation,
    Criterion,
    Evaluation,
    InputSpec,
    checked_total,
    fmt_number,
)
from medagent.models import Severity
from medagent.safety.child_pugh_liver_severity_scorer import (
    ChildPughFactors,
    ChildPughLiverSeverityScorer,
)
from medagent.safety.meld_na_scorer import MeldNaFactors, MeldNaScorer, compute_meld_na

INF = math.inf


def _evaluate_meld_na(values: Mapping[str, Any]) -> Evaluation:
    dialysis = values["dialysis"]
    result = compute_meld_na(
        bilirubin_mg_dl=values["bilirubin"],
        inr=values["inr"],
        creatinine_mg_dl=values["creatinine"],
        sodium_mmol_l=values["sodium"],
        dialysis=dialysis,
    )
    finding = MeldNaScorer().check(
        MeldNaFactors(
            bilirubin_mg_dl=values["bilirubin"],
            inr=values["inr"],
            creatinine_mg_dl=values["creatinine"],
            sodium_mmol_l=values["sodium"],
            dialysis=int(dialysis),
        )
    )[0]
    if finding.score != result.meld_na:
        raise RuntimeError("meld_na: scorer total disagrees with the derived terms")
    creatinine_note = "dialysis: set to 4.0" if dialysis else "bounded 1.0-4.0"
    terms = (
        ("creatinine", "0.957 x ln(creatinine)", 0.957, result.creatinine_mg_dl, creatinine_note),
        ("bilirubin", "0.378 x ln(bilirubin)", 0.378, result.bilirubin_mg_dl, "floor 1.0"),
        ("inr", "1.120 x ln(INR)", 1.120, result.inr, "floor 1.0"),
    )
    components = [
        Criterion(
            name,
            label,
            None,
            f"{name} {fmt_number(values[name])} -> {fmt_number(used)} ({note}): {label} = "
            f"{coefficient * math.log(used):.3f}",
            ("creatinine", "dialysis") if name == "creatinine" else (name,),
            value=round(coefficient * math.log(used), 3),
        )
        for name, label, coefficient, used, note in terms
    ]
    meld_raw = sum(coefficient * math.log(used) for _, _, coefficient, used, _ in terms) + 0.643
    components.append(
        Criterion(
            "meld_i",
            "MELD(i): sum of terms + 0.643, rounded to the tenth, x 10",
            None,
            " + ".join(f"{c.value:.3f}" for c in components)
            + f" + 0.643 = {meld_raw:.3f} -> {result.meld / 10:.1f} x 10 = MELD(i) {result.meld}",
            ("creatinine", "bilirubin", "inr", "dialysis"),
            value=result.meld,
        )
    )
    sodium_term = 0.0
    if result.meld > 11:
        gap = 137 - result.sodium_mmol_l
        sodium_term = 1.32 * gap - 0.033 * result.meld * gap
        shown, used, gap_text = (
            fmt_number(values["sodium"]),
            fmt_number(result.sodium_mmol_l),
            fmt_number(gap),
        )
        sodium_rule = (
            f"sodium {shown} -> {used} (bounded 125-137): "
            f"1.32 x {gap_text} - 0.033 x {result.meld} x {gap_text} = {sodium_term:.3f}"
        )
    else:
        sodium_rule = f"MELD(i) {result.meld} <= 11: sodium term not applied"
    components.append(
        Criterion(
            "sodium",
            "Sodium term (only when MELD(i) > 11)",
            None,
            sodium_rule,
            ("sodium",),
            value=round(sodium_term, 3),
        )
    )
    band = (
        "meld_ge_40"
        if result.meld_na >= 40
        else "meld_30_39"
        if result.meld_na >= 30
        else "meld_20_29"
        if result.meld_na >= 20
        else "meld_10_19"
        if result.meld_na >= 10
        else "meld_lt_10"
    )
    details = {"meld_i": result.meld, "sodium_term_applied": result.meld > 11}
    return Evaluation(result.meld_na, tuple(components), band, details)


MELD_NA = Calculator(
    id="meld_na",
    name="MELD-Na (Model for End-Stage Liver Disease with sodium)",
    version="1.0.0",
    category="hepatology",
    purpose="3-month mortality risk in chronic liver disease (OPTN 2016 MELD-Na).",
    inputs=(
        common.bilirubin(),
        common.inr(),
        common.creatinine(),
        InputSpec(
            "sodium",
            "Serum sodium",
            "number",
            "Serum sodium.",
            unit="mmol/L",
            alternative_units=(common.SODIUM_MEQ,),
            minimum=100,
            maximum=180,
        ),
        common.boolean(
            "dialysis",
            "Dialysis",
            "Dialysis at least twice, or >= 24 h of CVVHD, in the past 7 days.",
        ),
    ),
    bands=(
        Band(
            "meld_lt_10",
            "MELD < 10",
            "6-9",
            "3-month mortality 1.9% for MELD < 9 (Wiesner 2003).",
            Severity.LOW,
        ),
        Band(
            "meld_10_19",
            "MELD 10-19",
            "10-19",
            "3-month mortality 6.0% (Wiesner 2003).",
            Severity.MODERATE,
        ),
        Band(
            "meld_20_29",
            "MELD 20-29",
            "20-29",
            "3-month mortality 19.6% (Wiesner 2003).",
            Severity.HIGH,
        ),
        Band(
            "meld_30_39",
            "MELD 30-39",
            "30-39",
            "3-month mortality 52.6% (Wiesner 2003).",
            Severity.HIGH,
        ),
        Band(
            "meld_ge_40",
            "MELD >= 40",
            "40",
            "3-month mortality 71.3% (Wiesner 2003).",
            Severity.CRITICAL,
        ),
    ),
    citations=(
        Citation(
            "Kim WR, Biggins SW, Kremers WK, et al. Hyponatremia and mortality among patients "
            "on the liver-transplant waiting list. N Engl J Med. 2008;359(10):1018-1026.",
            doi="10.1056/NEJMoa0801209",
            pmid="18768945",
        ),
        Citation(
            "Wiesner R, Edwards E, Freeman R, et al. Model for end-stage liver disease (MELD) and "
            "allocation of donor livers. Gastroenterology. 2003;124(1):91-96.",
            doi="10.1053/gast.2003.50016",
            pmid="12512033",
        ),
    ),
    limitations=(
        "OPTN replaced MELD-Na with MELD 3.0 for US liver allocation in 2023; MELD 3.0 is not "
        "implemented here.",
        "Mortality strata come from the MELD (pre-sodium) waiting-list cohort of Wiesner 2003.",
        "Rounding follows OPTN: MELD(i) to the tenth, then x 10, and the final score half-up "
        "to an integer.",
    ),
    evaluate=_evaluate_meld_na,
    score_range="6-40",
    wraps="MeldNaScorer",
)


_ASCITES = {"none": 1, "slight": 2, "moderate_to_severe": 3}
_ENCEPHALOPATHY = {"none": 1, "grade_1_2": 2, "grade_3_4": 3}


def _three_level(value: float, low: float, high: float) -> int:
    """1 point below ``low``, 2 from ``low`` to ``high`` inclusive, 3 above ``high``."""
    if value < low:
        return 1
    return 2 if value <= high else 3


def _evaluate_child_pugh(values: Mapping[str, Any]) -> Evaluation:
    bilirubin, albumin, inr = values["bilirubin"], values["albumin"], values["inr"]
    bilirubin_points = _three_level(bilirubin, 2.0, 3.0)
    inr_points = _three_level(inr, 1.7, 2.3)
    albumin_points = 1 if albumin > 3.5 else 2 if albumin >= 2.8 else 3
    ascites, encephalopathy = _ASCITES[values["ascites"]], _ENCEPHALOPATHY[values["encephalopathy"]]
    components = (
        Criterion(
            "bilirubin",
            "Total bilirubin < 2 (+1), 2-3 (+2), > 3 mg/dL (+3)",
            bilirubin_points,
            f"bilirubin {fmt_number(bilirubin)} mg/dL in "
            f"{('< 2', '2-3', '> 3')[bilirubin_points - 1]}: +{bilirubin_points}",
            ("bilirubin",),
        ),
        Criterion(
            "albumin",
            "Albumin > 3.5 (+1), 2.8-3.5 (+2), < 2.8 g/dL (+3)",
            albumin_points,
            f"albumin {fmt_number(albumin)} g/dL in "
            f"{('> 3.5', '2.8-3.5', '< 2.8')[albumin_points - 1]}: +{albumin_points}",
            ("albumin",),
        ),
        Criterion(
            "inr",
            "INR < 1.7 (+1), 1.7-2.3 (+2), > 2.3 (+3)",
            inr_points,
            f"inr {fmt_number(inr)} in {('< 1.7', '1.7-2.3', '> 2.3')[inr_points - 1]}: "
            f"+{inr_points}",
            ("inr",),
        ),
        Criterion(
            "ascites", "Ascites", ascites, f"ascites {values['ascites']}: +{ascites}", ("ascites",)
        ),
        Criterion(
            "encephalopathy",
            "Hepatic encephalopathy",
            encephalopathy,
            f"encephalopathy {values['encephalopathy']}: +{encephalopathy}",
            ("encephalopathy",),
        ),
    )
    factors = ChildPughFactors(
        bilirubin_points=bilirubin_points,
        albumin_points=albumin_points,
        inr_points=inr_points,
        ascites_points=ascites,
        encephalopathy_points=encephalopathy,
    )
    finding = ChildPughLiverSeverityScorer().check(factors)[0]
    score = checked_total("child_pugh", finding.score, components)
    return Evaluation(score, components, f"class_{finding.child_class.lower()}")


CHILD_PUGH = Calculator(
    id="child_pugh",
    name="Child-Pugh score (cirrhosis severity)",
    version="1.0.0",
    category="hepatology",
    purpose="Severity class A/B/C of chronic liver disease (cirrhosis).",
    inputs=(
        common.bilirubin(),
        InputSpec(
            "albumin",
            "Serum albumin",
            "number",
            "Serum albumin.",
            unit="g/dL",
            alternative_units=(common.ALBUMIN_G_L,),
            minimum=0.5,
            maximum=7,
        ),
        common.inr(),
        InputSpec(
            "ascites",
            "Ascites",
            "choice",
            "Ascites: none, slight (mild or controlled), moderate to severe (tense or refractory).",
            choices=(
                Choice("none", "None (+1)"),
                Choice("slight", "Slight (+2)"),
                Choice("moderate_to_severe", "Moderate to severe (+3)"),
            ),
        ),
        InputSpec(
            "encephalopathy",
            "Hepatic encephalopathy",
            "choice",
            "Hepatic encephalopathy grade (West Haven).",
            choices=(
                Choice("none", "None (+1)"),
                Choice("grade_1_2", "Grade 1-2 (+2)"),
                Choice("grade_3_4", "Grade 3-4 (+3)"),
            ),
        ),
    ),
    bands=(
        Band("class_a", "Child-Pugh class A", "5-6", "Well-compensated disease.", Severity.LOW),
        Band(
            "class_b",
            "Child-Pugh class B",
            "7-9",
            "Significant functional compromise.",
            Severity.MODERATE,
        ),
        Band("class_c", "Child-Pugh class C", "10-15", "Decompensated disease.", Severity.HIGH),
    ),
    citations=(
        Citation(
            "Pugh RN, Murray-Lyon IM, Dawson JL, Pietroni MC, Williams R. Transection of the "
            "oesophagus for bleeding oesophageal varices. Br J Surg. 1973;60(8):646-649.",
            doi="10.1002/bjs.1800600817",
            pmid="4541913",
        ),
    ),
    limitations=(
        "The INR cut-offs (< 1.7, 1.7-2.3, > 2.3) replace the prothrombin-time prolongation of "
        "the 1973 score, as in current practice; INR is not standardised for liver disease.",
        "Cholestatic disease (PBC/PSC) uses higher bilirubin cut-offs, not implemented here.",
        "Ascites and encephalopathy grades are clinician judgements.",
    ),
    evaluate=_evaluate_child_pugh,
    score_range="5-15",
    wraps="ChildPughLiverSeverityScorer",
)


def _round_half_up(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def ckd_epi_2021_egfr(creatinine_mg_dl: float, age: int, female: bool) -> float:
    """Race-free CKD-EPI 2021 creatinine eGFR (mL/min/1.73 m2), unrounded (Inker 2021)."""
    kappa, alpha = (0.7, -0.241) if female else (0.9, -0.302)
    ratio = creatinine_mg_dl / kappa
    sex_factor = 1.012 if female else 1.0
    egfr: float = 142 * min(ratio, 1) ** alpha * max(ratio, 1) ** -1.200 * 0.9938**age
    return egfr * sex_factor


_KDIGO_G = (
    (90, "g1"),
    (60, "g2"),
    (45, "g3a"),
    (30, "g3b"),
    (15, "g4"),
)


def _evaluate_ckd_epi(values: Mapping[str, Any]) -> Evaluation:
    creatinine, age, female = values["creatinine"], values["age"], values["sex"] == "female"
    kappa, alpha = (0.7, -0.241) if female else (0.9, -0.302)
    ratio = creatinine / kappa
    min_term, max_term = min(ratio, 1) ** alpha, max(ratio, 1) ** -1.200
    age_factor, sex_factor = 0.9938**age, 1.012 if female else 1.0
    egfr = ckd_epi_2021_egfr(creatinine, age, female)
    rounded = _round_half_up(egfr)
    components = (
        Criterion(
            "creatinine_ratio",
            "Scr / kappa (kappa 0.7 female, 0.9 male)",
            None,
            f"creatinine {fmt_number(creatinine)} mg/dL / {kappa} = {ratio:.4f}",
            ("creatinine", "sex"),
            value=round(ratio, 4),
        ),
        Criterion(
            "min_term",
            "min(Scr/kappa, 1) ^ alpha (alpha -0.241 female, -0.302 male)",
            None,
            f"min({ratio:.4f}, 1) ^ {alpha} = {min_term:.4f}",
            ("creatinine", "sex"),
            value=round(min_term, 4),
        ),
        Criterion(
            "max_term",
            "max(Scr/kappa, 1) ^ -1.200",
            None,
            f"max({ratio:.4f}, 1) ^ -1.200 = {max_term:.4f}",
            ("creatinine", "sex"),
            value=round(max_term, 4),
        ),
        Criterion(
            "age_factor",
            "0.9938 ^ age",
            None,
            f"0.9938 ^ {age} = {age_factor:.4f}",
            ("age",),
            value=round(age_factor, 4),
        ),
        Criterion(
            "sex_factor",
            "x 1.012 if female",
            None,
            f"sex {values['sex']}: x {sex_factor}",
            ("sex",),
            value=sex_factor,
        ),
        Criterion(
            "egfr",
            "142 x min term x max term x age factor x sex factor",
            None,
            f"142 x {min_term:.4f} x {max_term:.4f} x {age_factor:.4f} x {sex_factor} = "
            f"{egfr:.2f} (reported as {rounded})",
            ("creatinine", "age", "sex"),
            value=egfr,
        ),
    )
    # The band and the score keep full precision: rounding first would move 59.8 into G2
    # and could cross the inclusive eGFR thresholds of the renal dosing checks.
    band = next((name for lower, name in _KDIGO_G if egfr >= lower), "g5")
    return Evaluation(egfr, components, band, {"egfr_rounded": rounded})


CKD_EPI_2021 = Calculator(
    id="ckd_epi_2021",
    name="CKD-EPI 2021 creatinine eGFR (race-free)",
    version="1.0.0",
    category="nephrology",
    purpose="Estimated GFR of adults from serum creatinine, age and sex without a race term.",
    inputs=(
        common.creatinine(),
        common.age(),
        common.sex(),
    ),
    bands=(
        Band(
            "g1",
            "G1 normal or high",
            ">= 90",
            "KDIGO GFR category G1 (CKD only with markers of kidney damage).",
            Severity.LOW,
        ),
        Band("g2", "G2 mildly decreased", "60-89", "KDIGO GFR category G2.", Severity.LOW),
        Band(
            "g3a",
            "G3a mildly to moderately decreased",
            "45-59",
            "KDIGO GFR category G3a.",
            Severity.MODERATE,
        ),
        Band(
            "g3b",
            "G3b moderately to severely decreased",
            "30-44",
            "KDIGO GFR category G3b.",
            Severity.MODERATE,
        ),
        Band("g4", "G4 severely decreased", "15-29", "KDIGO GFR category G4.", Severity.HIGH),
        Band("g5", "G5 kidney failure", "< 15", "KDIGO GFR category G5.", Severity.CRITICAL),
    ),
    citations=(
        Citation(
            "Inker LA, Eneanya ND, Coresh J, et al. New creatinine- and cystatin C-based "
            "equations to estimate GFR without race. N Engl J Med. 2021;385(19):1737-1749.",
            doi="10.1056/NEJMoa2102953",
            pmid="34554658",
        ),
        Citation(
            "Kidney Disease: Improving Global Outcomes (KDIGO) CKD Work Group. KDIGO 2012 "
            "clinical practice guideline for the evaluation and management of chronic kidney "
            "disease. Kidney Int Suppl. 2013;3(1):1-150.",
            url="https://kdigo.org/guidelines/ckd-evaluation-and-management/",
        ),
    ),
    limitations=(
        "Assumes a stable serum creatinine; not valid in acute kidney injury, pregnancy, "
        "extremes of muscle mass or diet, or for children (< 18 years).",
        "eGFR is normalised to 1.73 m2 body-surface area; drug-dosing references may require "
        "an absolute GFR or Cockcroft-Gault creatinine clearance instead.",
        "A G category alone is not a CKD diagnosis (KDIGO needs > 3 months and albuminuria).",
    ),
    evaluate=_evaluate_ckd_epi,
    score_unit="mL/min/1.73 m2",
    score_range="> 0",
)
