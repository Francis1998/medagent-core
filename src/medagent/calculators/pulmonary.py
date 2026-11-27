"""CURB-65, Wells PE and PERC calculators wrapping the audited safety scorers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from medagent.calculators import inputs as common
from medagent.calculators.base import (
    Band,
    Calculator,
    Citation,
    Criterion,
    Evaluation,
    InputSpec,
    checked_total,
    flag,
    threshold,
)
from medagent.models import Severity
from medagent.safety.curb65_pneumonia_scorer import Curb65Factors, Curb65PneumoniaScorer
from medagent.safety.perc_pe_exclusion_scorer import PercPeExclusionScorer, PercPeFactors
from medagent.safety.wells_pe_probability_scorer import WellsPeFactors, WellsPeProbabilityScorer


def _evaluate_curb65(values: Mapping[str, Any]) -> Evaluation:
    urea, rr, age = values["urea"], values["respiratory_rate"], values["age"]
    sbp, dbp = values["systolic_bp"], values["diastolic_bp"]
    low_bp = sbp < 90 or dbp <= 60
    bp_rule = (
        f"systolic_bp {sbp} mmHg {'<' if sbp < 90 else '>='} 90; diastolic_bp {dbp} mmHg "
        f"{'<=' if dbp <= 60 else '>'} 60: {'+1' if low_bp else '0'}"
    )
    components = (
        flag("confusion", "Confusion (new disorientation)", values["confusion"], 1, "confusion"),
        threshold(
            "urea_over_7",
            "Urea > 7 mmol/L (BUN > 19.6 mg/dL)",
            input_name="urea",
            value=urea,
            unit="mmol/L",
            met=urea > 7,
            met_text="> 7",
            unmet_text="<= 7",
            points=1,
        ),
        threshold(
            "resp_rate_30_plus",
            "Respiratory rate >= 30/min",
            input_name="respiratory_rate",
            value=rr,
            unit="/min",
            met=rr >= 30,
            met_text=">= 30",
            unmet_text="< 30",
            points=1,
        ),
        Criterion(
            "low_blood_pressure",
            "Systolic BP < 90 or diastolic BP <= 60 mmHg",
            1 if low_bp else 0,
            bp_rule,
            ("systolic_bp", "diastolic_bp"),
        ),
        threshold(
            "age_65_plus",
            "Age >= 65 years",
            input_name="age",
            value=age,
            unit="years",
            met=age >= 65,
            met_text=">= 65",
            unmet_text="< 65",
            points=1,
        ),
    )
    fired = {c.criterion: c.earned > 0 for c in components}
    finding = Curb65PneumoniaScorer().check(Curb65Factors(**fired))[0]
    return Evaluation(checked_total("curb_65", finding.score, components), components, finding.band)


CURB_65 = Calculator(
    id="curb_65",
    name="CURB-65 (community-acquired pneumonia severity)",
    version="1.0.0",
    category="pulmonology",
    purpose="30-day mortality risk of adults presenting with community-acquired pneumonia.",
    inputs=(
        common.boolean(
            "confusion",
            "Confusion",
            "New mental confusion (disorientation in person, place or time; AMT <= 8).",
        ),
        InputSpec(
            "urea",
            "Serum urea",
            "number",
            "Serum urea in mmol/L, or blood urea nitrogen (BUN) in mg/dL.",
            unit="mmol/L",
            alternative_units=(common.BUN_MG_DL,),
            minimum=0.5,
            maximum=100,
        ),
        common.respiratory_rate(),
        common.systolic_bp(),
        InputSpec(
            "diastolic_bp",
            "Diastolic blood pressure",
            "integer",
            "Diastolic blood pressure.",
            unit="mmHg",
            minimum=10,
            maximum=200,
        ),
        common.age(),
    ),
    bands=(
        Band(
            "mild",
            "Low risk",
            "0-1",
            "30-day mortality 0.7% (score 0) and 3.2% (score 1) in the derivation cohort "
            "(Lim 2003).",
            Severity.LOW,
        ),
        Band(
            "moderate",
            "Intermediate risk",
            "2",
            "Intermediate-risk group; mortality rises with each point (Lim 2003).",
            Severity.MODERATE,
        ),
        Band(
            "severe",
            "High risk",
            "3-5",
            "30-day mortality 17% (score 3), 41.5% (score 4) and 57% (score 5) in the "
            "derivation cohort (Lim 2003).",
            Severity.HIGH,
        ),
    ),
    citations=(
        Citation(
            "Lim WS, van der Eerden MM, Laing R, et al. Defining community acquired pneumonia "
            "severity on presentation to hospital: an international derivation and validation "
            "study. Thorax. 2003;58(5):377-382.",
            doi="10.1136/thorax.58.5.377",
            pmid="12728155",
        ),
    ),
    limitations=(
        "Validated in adults with community-acquired pneumonia; not for hospital-acquired "
        "pneumonia or immunocompromised patients.",
        "BUN is converted exactly (urea mmol/L = BUN mg/dL x 0.357, so 7 mmol/L = 19.6 mg/dL); "
        "MDCalc's rounded 'BUN > 19 mg/dL' scores 19.1-19.6 mg/dL differently.",
        "Confusion is a clinical judgement the caller must supply; the score does not capture "
        "comorbidities, hypoxaemia or social factors.",
    ),
    evaluate=_evaluate_curb65,
    score_range="0-5",
    wraps="Curb65PneumoniaScorer",
)


def _evaluate_wells_pe(values: Mapping[str, Any]) -> Evaluation:
    hr = values["heart_rate"]
    components = (
        flag(
            "clinical_dvt_signs",
            "Clinical signs of DVT",
            values["clinical_dvt_signs"],
            3,
            "clinical_dvt_signs",
        ),
        flag(
            "pe_most_likely",
            "PE is the most likely diagnosis",
            values["pe_most_likely_diagnosis"],
            3,
            "pe_most_likely_diagnosis",
        ),
        threshold(
            "heart_rate_over_100",
            "Heart rate > 100/min",
            input_name="heart_rate",
            value=hr,
            unit="/min",
            met=hr > 100,
            met_text="> 100",
            unmet_text="<= 100",
            points=1.5,
        ),
        flag(
            "immobilization_or_surgery",
            "Immobilisation >= 3 days or surgery in the previous 4 weeks",
            values["immobilization_or_recent_surgery"],
            1.5,
            "immobilization_or_recent_surgery",
        ),
        flag(
            "previous_dvt_pe",
            "Previous DVT or PE",
            values["previous_dvt_or_pe"],
            1.5,
            "previous_dvt_or_pe",
        ),
        flag("hemoptysis", "Haemoptysis", values["hemoptysis"], 1, "hemoptysis"),
        flag(
            "malignancy",
            "Malignancy (treatment within 6 months or palliative)",
            values["malignancy"],
            1,
            "malignancy",
        ),
    )
    fired = {c.criterion: c.earned > 0 for c in components}
    finding = WellsPeProbabilityScorer().check(WellsPeFactors(**fired))[0]
    score = checked_total("wells_pe", finding.score, components)
    two_tier = "pe_likely" if score > 4 else "pe_unlikely"
    return Evaluation(score, components, finding.band, {"two_tier": two_tier})


WELLS_PE = Calculator(
    id="wells_pe",
    name="Wells criteria for pulmonary embolism",
    version="1.0.0",
    category="pulmonology",
    purpose="Pretest probability of pulmonary embolism (three-tier and two-tier models).",
    inputs=(
        common.boolean(
            "clinical_dvt_signs",
            "Clinical signs of DVT",
            "Leg swelling and pain with palpation of the deep veins.",
        ),
        common.boolean(
            "pe_most_likely_diagnosis",
            "PE most likely diagnosis",
            "PE is the most likely diagnosis, or equally likely (clinician gestalt).",
        ),
        common.heart_rate(),
        common.boolean(
            "immobilization_or_recent_surgery",
            "Immobilisation or recent surgery",
            "Immobilisation for >= 3 days or surgery in the previous 4 weeks.",
        ),
        common.boolean(
            "previous_dvt_or_pe", "Previous DVT or PE", "Objectively diagnosed DVT or PE."
        ),
        common.boolean("hemoptysis", "Haemoptysis", "Haemoptysis."),
        common.boolean(
            "malignancy",
            "Malignancy",
            "Cancer treated within the past 6 months or receiving palliative care.",
        ),
    ),
    bands=(
        Band(
            "low", "Low probability", "< 2", "Low pretest probability (Wells 2000).", Severity.LOW
        ),
        Band(
            "moderate",
            "Moderate probability",
            "2-6",
            "Moderate pretest probability; 6.0 is still moderate (Wells 2000).",
            Severity.MODERATE,
        ),
        Band(
            "high",
            "High probability",
            "> 6",
            "High pretest probability (Wells 2000).",
            Severity.HIGH,
        ),
    ),
    citations=(
        Citation(
            "Wells PS, Anderson DR, Rodger M, et al. Derivation of a simple clinical model to "
            "categorize patients probability of pulmonary embolism: increasing the models utility "
            "with the SimpliRED D-dimer. Thromb Haemost. 2000;83(3):416-420.",
            pmid="10744147",
        ),
    ),
    limitations=(
        "Two criteria are clinician judgements (DVT signs, PE most likely); the score inherits "
        "their subjectivity.",
        "The dichotomised model is reported as details.two_tier (pe_unlikely <= 4, pe_likely > 4; "
        "7.8% of 'unlikely' patients had PE in the derivation set) next to the three-tier bands.",
        "Not validated in pregnancy.",
    ),
    evaluate=_evaluate_wells_pe,
    score_range="0-12.5",
    wraps="WellsPeProbabilityScorer",
)


def _evaluate_perc(values: Mapping[str, Any]) -> Evaluation:
    age, hr, spo2 = values["age"], values["heart_rate"], values["oxygen_saturation"]
    components = (
        threshold(
            "age_ge_50",
            "Age >= 50 years",
            input_name="age",
            value=age,
            unit="years",
            met=age >= 50,
            met_text=">= 50",
            unmet_text="< 50",
            points=1,
        ),
        threshold(
            "hr_ge_100",
            "Heart rate >= 100/min",
            input_name="heart_rate",
            value=hr,
            unit="/min",
            met=hr >= 100,
            met_text=">= 100",
            unmet_text="< 100",
            points=1,
        ),
        threshold(
            "o2_sat_lt_95",
            "SpO2 < 95% on room air",
            input_name="oxygen_saturation",
            value=spo2,
            unit="%",
            met=spo2 < 95,
            met_text="< 95",
            unmet_text=">= 95",
            points=1,
        ),
        flag(
            "unilateral_leg_swelling",
            "Unilateral leg swelling",
            values["unilateral_leg_swelling"],
            1,
            "unilateral_leg_swelling",
        ),
        flag("hemoptysis", "Haemoptysis", values["hemoptysis"], 1, "hemoptysis"),
        flag(
            "recent_surgery_or_trauma",
            "Surgery or trauma within 4 weeks",
            values["recent_surgery_or_trauma"],
            1,
            "recent_surgery_or_trauma",
        ),
        flag("prior_pe_or_dvt", "Prior PE or DVT", values["prior_pe_or_dvt"], 1, "prior_pe_or_dvt"),
        flag("hormone_use", "Hormone use", values["hormone_use"], 1, "hormone_use"),
    )
    fired = {c.criterion: int(c.earned > 0) for c in components}
    finding = PercPeExclusionScorer().check(PercPeFactors(**fired))[0]
    score = checked_total("perc", finding.score, components)
    return Evaluation(score, components, "perc_negative" if score == 0 else "perc_positive")


PERC = Calculator(
    id="perc",
    name="PERC rule for pulmonary embolism",
    version="1.0.0",
    category="pulmonology",
    purpose="Pulmonary Embolism Rule-out Criteria for patients with a low pretest probability.",
    inputs=(
        common.age(),
        common.heart_rate(),
        common.oxygen_saturation("SpO2 on room air."),
        common.boolean(
            "unilateral_leg_swelling", "Unilateral leg swelling", "Unilateral leg swelling."
        ),
        common.boolean("hemoptysis", "Haemoptysis", "Haemoptysis."),
        common.boolean(
            "recent_surgery_or_trauma",
            "Recent surgery or trauma",
            "Surgery or trauma within 4 weeks requiring general anaesthesia (or hospitalisation).",
        ),
        common.boolean("prior_pe_or_dvt", "Prior PE or DVT", "History of PE or DVT."),
        common.boolean(
            "hormone_use",
            "Hormone use",
            "Oral contraceptives, hormone replacement or oestrogen use.",
        ),
    ),
    bands=(
        Band(
            "perc_negative",
            "PERC negative (all 8 criteria absent)",
            "0",
            "Rule-out criteria met. Kline 2004 reported a false-negative rate below 2% only in "
            "patients whose clinical pretest probability was already low (gestalt < 15%).",
            Severity.LOW,
        ),
        Band(
            "perc_positive",
            "PERC positive (>= 1 criterion present)",
            "1-8",
            "PE cannot be excluded by PERC; the rule does not estimate PE probability.",
            Severity.MODERATE,
        ),
    ),
    citations=(
        Citation(
            "Kline JA, Mitchell AM, Kabrhel C, Richman PB, Courtney DM. Clinical criteria to "
            "prevent unnecessary diagnostic testing in emergency department patients with "
            "suspected pulmonary embolism. J Thromb Haemost. 2004;2(8):1247-1255.",
            doi="10.1111/j.1538-7836.2004.00790.x",
            pmid="15304025",
        ),
    ),
    limitations=(
        "Only meaningful when clinical pretest probability is already low; PERC is not a risk "
        "score and a negative result is meaningless in moderate- or high-probability patients.",
        "The wrapped PercPeExclusionScorer also labels one criterion 'near_miss'; the calculator "
        "reports the published two-way interpretation.",
    ),
    evaluate=_evaluate_perc,
    score_range="0-8",
    wraps="PercPeExclusionScorer",
)
