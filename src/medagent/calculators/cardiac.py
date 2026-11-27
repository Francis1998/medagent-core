"""CHA2DS2-VASc, HAS-BLED and HEART calculators wrapping the audited safety scorers."""

from __future__ import annotations

from collections.abc import Mapping
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
    flag,
    threshold,
)
from medagent.models import Severity
from medagent.safety.cha2ds2_vasc_stroke_risk_scorer import (
    Cha2ds2VascFactors,
    Cha2ds2VascStrokeRiskScorer,
)
from medagent.safety.has_bled_bleed_risk_scorer import HasBledBleedRiskScorer, HasBledFactors
from medagent.safety.heart_score_acs_scorer import HeartScoreAcsScorer, HeartScoreFactors


def _evaluate_cha2ds2_vasc(values: Mapping[str, Any]) -> Evaluation:
    age = values["age"]
    age_points = 2 if age >= 75 else 1 if age >= 65 else 0
    age_rule = f"age {age} years {'>= 75' if age >= 75 else '65-74' if age >= 65 else '< 65'}"
    female = values["sex"] == "female"
    components = (
        flag(
            "congestive_hf",
            "Congestive heart failure",
            values["congestive_heart_failure"],
            1,
            "congestive_heart_failure",
        ),
        flag("hypertension", "Hypertension", values["hypertension"], 1, "hypertension"),
        Criterion(
            "age",
            "Age 65-74 (+1) or >= 75 years (+2)",
            age_points,
            f"{age_rule}: {'+' + str(age_points) if age_points else '0'}",
            ("age",),
        ),
        flag("diabetes", "Diabetes mellitus", values["diabetes"], 1, "diabetes"),
        flag(
            "stroke_tia_thromboembolism",
            "Prior stroke, TIA or thromboembolism",
            values["stroke_tia_thromboembolism"],
            2,
            "stroke_tia_thromboembolism",
        ),
        flag(
            "vascular_disease",
            "Vascular disease",
            values["vascular_disease"],
            1,
            "vascular_disease",
        ),
        Criterion(
            "female_sex",
            "Sex category (female)",
            1 if female else 0,
            f"sex {values['sex']}: {'+1' if female else '0'}",
            ("sex",),
        ),
    )
    factors = Cha2ds2VascFactors(
        congestive_hf=values["congestive_heart_failure"],
        hypertension=values["hypertension"],
        age_ge_75=age >= 75,
        age_65_to_74=65 <= age < 75,
        diabetes=values["diabetes"],
        stroke_tia_thromboembolism=values["stroke_tia_thromboembolism"],
        vascular_disease=values["vascular_disease"],
        female_sex=female,
    )
    finding = Cha2ds2VascStrokeRiskScorer().check(factors)[0]
    score = checked_total("cha2ds2_vasc", finding.score, components)
    return Evaluation(score, components, finding.band)


CHA2DS2_VASC = Calculator(
    id="cha2ds2_vasc",
    name="CHA2DS2-VASc (stroke risk in atrial fibrillation)",
    version="1.0.0",
    category="cardiology",
    purpose="Stroke and thromboembolism risk stratification in non-valvular atrial fibrillation.",
    inputs=(
        common.age(),
        common.sex(),
        common.boolean(
            "congestive_heart_failure",
            "Congestive heart failure",
            "Heart failure or objective moderate-severe LV dysfunction.",
        ),
        common.boolean("hypertension", "Hypertension", "History of hypertension."),
        common.boolean("diabetes", "Diabetes mellitus", "Diabetes mellitus."),
        common.boolean(
            "stroke_tia_thromboembolism",
            "Stroke / TIA / thromboembolism",
            "Prior stroke, transient ischaemic attack or thromboembolism.",
        ),
        common.boolean(
            "vascular_disease",
            "Vascular disease",
            "Prior myocardial infarction, peripheral artery disease or aortic plaque.",
        ),
    ),
    bands=(
        Band(
            "low", "Low risk", "0", "Lowest thromboembolic-risk stratum (Lip 2010).", Severity.LOW
        ),
        Band(
            "moderate",
            "Intermediate risk",
            "1",
            "Intermediate thromboembolic-risk stratum (Lip 2010).",
            Severity.MODERATE,
        ),
        Band(
            "high",
            "High risk",
            "2-9",
            "High thromboembolic-risk stratum (Lip 2010); risk rises with each point.",
            Severity.HIGH,
        ),
    ),
    citations=(
        Citation(
            "Lip GYH, Nieuwlaat R, Pisters R, Lane DA, Crijns HJGM. Refining clinical risk "
            "stratification for predicting stroke and thromboembolism in atrial fibrillation "
            "using a novel risk factor-based approach: the Euro Heart Survey on Atrial "
            "Fibrillation. Chest. 2010;137(2):263-272.",
            doi="10.1378/chest.09-1584",
            pmid="19762550",
        ),
    ),
    limitations=(
        "Bands follow Lip 2010. Later guidelines treat female sex as a risk modifier (a score "
        "of 1 from sex alone is low risk), and the ESC 2024 guideline uses CHA2DS2-VA without "
        "the sex point; compare against the guideline you work under.",
        "For non-valvular atrial fibrillation only (not mechanical valves or moderate-severe "
        "mitral stenosis).",
    ),
    evaluate=_evaluate_cha2ds2_vasc,
    score_range="0-9",
    wraps="Cha2ds2VascStrokeRiskScorer",
)


_HAS_BLED_FLAGS = (
    (
        "hypertension",
        "Uncontrolled hypertension (systolic > 160 mmHg)",
        "uncontrolled_hypertension",
    ),
    ("abnormal_renal", "Abnormal renal function", "abnormal_renal_function"),
    ("abnormal_liver", "Abnormal liver function", "abnormal_liver_function"),
    ("stroke_history", "Prior stroke", "stroke_history"),
    ("bleeding_history", "Major bleeding history or predisposition", "bleeding_history"),
    ("labile_inr", "Labile INR", "labile_inr"),
)


def _evaluate_has_bled(values: Mapping[str, Any]) -> Evaluation:
    age = values["age"]
    components = (
        *(
            flag(criterion, label, values[name], 1, name)
            for criterion, label, name in _HAS_BLED_FLAGS
        ),
        threshold(
            "elderly",
            "Elderly (age > 65 years)",
            input_name="age",
            value=age,
            unit="years",
            met=age > 65,
            met_text="> 65",
            unmet_text="<= 65",
            points=1,
        ),
        flag(
            "drugs",
            "Antiplatelet agents or NSAIDs",
            values["antiplatelet_or_nsaid"],
            1,
            "antiplatelet_or_nsaid",
        ),
        flag("alcohol", "Alcohol >= 8 drinks/week", values["alcohol_excess"], 1, "alcohol_excess"),
    )
    fired = {c.criterion: c.earned > 0 for c in components}
    finding = HasBledBleedRiskScorer().check(HasBledFactors(**fired))[0]
    return Evaluation(
        checked_total("has_bled", finding.score, components), components, finding.band
    )


HAS_BLED = Calculator(
    id="has_bled",
    name="HAS-BLED (major bleeding risk on anticoagulation)",
    version="1.0.0",
    category="cardiology",
    purpose="1-year major bleeding risk of patients with atrial fibrillation on anticoagulation.",
    inputs=(
        common.age(),
        common.boolean(
            "uncontrolled_hypertension",
            "Uncontrolled hypertension",
            "Uncontrolled hypertension, systolic blood pressure > 160 mmHg.",
        ),
        common.boolean(
            "abnormal_renal_function",
            "Abnormal renal function",
            "Chronic dialysis, renal transplant or serum creatinine >= 2.26 mg/dL (200 µmol/L).",
        ),
        common.boolean(
            "abnormal_liver_function",
            "Abnormal liver function",
            "Cirrhosis, or bilirubin > 2x ULN with AST/ALT/ALP > 3x ULN.",
        ),
        common.boolean("stroke_history", "Prior stroke", "History of stroke."),
        common.boolean(
            "bleeding_history",
            "Bleeding history",
            "Prior major bleeding or predisposition to bleeding (e.g. anaemia, thrombocytopenia).",
        ),
        common.boolean(
            "labile_inr",
            "Labile INR",
            "Unstable or high INRs, or time in therapeutic range < 60% (vitamin K antagonists).",
        ),
        common.boolean(
            "antiplatelet_or_nsaid",
            "Antiplatelet agents or NSAIDs",
            "Concomitant antiplatelet agents or non-steroidal anti-inflammatory drugs.",
        ),
        common.boolean("alcohol_excess", "Alcohol use", ">= 8 alcoholic drinks per week."),
    ),
    bands=(
        Band(
            "low",
            "Low risk",
            "0-1",
            "1.13 (score 0) and 1.02 (score 1) major bleeds per 100 patient-years (Pisters 2010).",
            Severity.LOW,
        ),
        Band(
            "moderate",
            "Moderate risk",
            "2",
            "1.88 major bleeds per 100 patient-years (Pisters 2010).",
            Severity.MODERATE,
        ),
        Band(
            "high",
            "High risk",
            "3-9",
            "3.74 (score 3) to 12.5 (score 5) major bleeds per 100 patient-years (Pisters 2010).",
            Severity.HIGH,
        ),
    ),
    citations=(
        Citation(
            "Pisters R, Lane DA, Nieuwlaat R, de Vos CB, Crijns HJGM, Lip GYH. A novel "
            "user-friendly score (HAS-BLED) to assess 1-year risk of major bleeding in patients "
            "with atrial fibrillation: the Euro Heart Survey. Chest. 2010;138(5):1093-1100.",
            doi="10.1378/chest.10-0134",
            pmid="20299623",
        ),
    ),
    limitations=(
        "A high score flags modifiable bleeding risk factors for clinician review; the score "
        "alone does not determine therapy.",
        "Labile INR applies to vitamin K antagonists only.",
    ),
    evaluate=_evaluate_has_bled,
    score_range="0-9",
    wraps="HasBledBleedRiskScorer",
)


_HISTORY = {"slightly_suspicious": 0, "moderately_suspicious": 1, "highly_suspicious": 2}
_ECG = {"normal": 0, "nonspecific_repolarization": 1, "significant_st_deviation": 2}
_HEART_RISK_FACTORS = (
    "hypercholesterolemia",
    "hypertension",
    "diabetes",
    "smoking",
    "family_history",
    "obesity",
)


def _evaluate_heart(values: Mapping[str, Any]) -> Evaluation:
    history, ecg, age = _HISTORY[values["history"]], _ECG[values["ecg"]], values["age"]
    age_points = 2 if age >= 65 else 1 if age >= 45 else 0
    present = [name for name in _HEART_RISK_FACTORS if values[name]]
    atherosclerotic = values["atherosclerotic_disease"]
    risk_points = 2 if atherosclerotic or len(present) >= 3 else 1 if present else 0
    ratio = values["troponin"] / values["troponin_uln"]
    troponin_points = 2 if ratio > 3 else 1 if ratio > 1 else 0
    components = (
        Criterion(
            "history",
            "History",
            history,
            f"history {values['history']}: {_pts(history)}",
            ("history",),
        ),
        Criterion("ecg", "ECG", ecg, f"ecg {values['ecg']}: {_pts(ecg)}", ("ecg",)),
        Criterion(
            "age",
            "Age < 45 (0), 45-64 (+1), >= 65 years (+2)",
            age_points,
            f"age {age} years {'>= 65' if age >= 65 else '45-64' if age >= 45 else '< 45'}: "
            f"{_pts(age_points)}",
            ("age",),
        ),
        Criterion(
            "risk_factors",
            "Risk factors: 1-2 (+1), >= 3 or known atherosclerotic disease (+2)",
            risk_points,
            f"{len(present)} risk factor(s) {present}; atherosclerotic_disease "
            f"{str(atherosclerotic).lower()}: {_pts(risk_points)}",
            (*_HEART_RISK_FACTORS, "atherosclerotic_disease"),
        ),
        Criterion(
            "troponin",
            "Troponin <= ULN (0), 1-3x ULN (+1), > 3x ULN (+2)",
            troponin_points,
            f"troponin / troponin_uln = {ratio:.2f} "
            f"{'> 3' if ratio > 3 else '> 1 and <= 3' if ratio > 1 else '<= 1'}: "
            f"{_pts(troponin_points)}",
            ("troponin", "troponin_uln"),
        ),
    )
    factors = HeartScoreFactors(history, ecg, age_points, risk_points, troponin_points)
    finding = HeartScoreAcsScorer().check(factors)[0]
    return Evaluation(checked_total("heart", finding.score, components), components, finding.band)


def _pts(points: int) -> str:
    return f"+{points}" if points else "0"


HEART = Calculator(
    id="heart",
    name="HEART score for major adverse cardiac events",
    version="1.0.0",
    category="cardiology",
    purpose="6-week risk of major adverse cardiac events in emergency patients with chest pain.",
    inputs=(
        InputSpec(
            "history",
            "History",
            "choice",
            "Clinician's assessment of how suspicious the history is for ACS.",
            choices=(
                Choice("slightly_suspicious", "Slightly suspicious (0)"),
                Choice("moderately_suspicious", "Moderately suspicious (+1)"),
                Choice("highly_suspicious", "Highly suspicious (+2)"),
            ),
        ),
        InputSpec(
            "ecg",
            "ECG",
            "choice",
            "Most abnormal ECG finding.",
            choices=(
                Choice("normal", "Normal (0)"),
                Choice(
                    "nonspecific_repolarization", "Non-specific repolarisation disturbance (+1)"
                ),
                Choice("significant_st_deviation", "Significant ST deviation (+2)"),
            ),
        ),
        common.age(),
        common.boolean("hypercholesterolemia", "Hypercholesterolaemia", "Hypercholesterolaemia."),
        common.boolean("hypertension", "Hypertension", "Hypertension."),
        common.boolean("diabetes", "Diabetes mellitus", "Diabetes mellitus."),
        common.boolean("smoking", "Smoking", "Current smoker or stopped within 3 months."),
        common.boolean(
            "family_history",
            "Family history",
            "Parent or sibling with cardiovascular disease before age 65.",
        ),
        common.boolean("obesity", "Obesity", "Body-mass index > 30 kg/m2."),
        common.boolean(
            "atherosclerotic_disease",
            "Known atherosclerotic disease",
            "Prior myocardial infarction, revascularisation, stroke or peripheral artery disease.",
        ),
        InputSpec(
            "troponin",
            "Troponin",
            "number",
            "Initial troponin, in the same unit as troponin_uln.",
            minimum=0,
            maximum=1_000_000,
        ),
        InputSpec(
            "troponin_uln",
            "Troponin upper reference limit",
            "number",
            "The assay's upper reference limit (99th percentile), same unit as troponin.",
            minimum=0.001,
            maximum=1_000_000,
        ),
    ),
    bands=(
        Band(
            "low",
            "Low risk",
            "0-3",
            "6-week MACE 2.5% in the derivation cohort (Six 2008).",
            Severity.LOW,
        ),
        Band(
            "moderate", "Moderate risk", "4-6", "6-week MACE 20.3% (Six 2008).", Severity.MODERATE
        ),
        Band("high", "High risk", "7-10", "6-week MACE 72.7% (Six 2008).", Severity.HIGH),
    ),
    citations=(
        Citation(
            "Six AJ, Backus BE, Kelder JC. Chest pain in the emergency room: value of the HEART "
            "score. Neth Heart J. 2008;16(6):191-196.",
            doi="10.1007/BF03086144",
            pmid="18665203",
        ),
    ),
    limitations=(
        "History and ECG are clinician judgements; the score is for undifferentiated chest pain "
        "without ST-elevation myocardial infarction.",
        "Troponin points use the ratio to the assay's upper reference limit; serial-troponin "
        "pathways (e.g. HEART pathway) are outside this calculator.",
    ),
    evaluate=_evaluate_heart,
    score_range="0-10",
    wraps="HeartScoreAcsScorer",
)
