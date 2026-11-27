"""qSOFA, NEWS2, GCS and Centor (McIsaac) calculators wrapping the audited safety scorers."""

from __future__ import annotations

import math
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
    banded,
    checked_total,
    flag,
    threshold,
)
from medagent.models import Severity
from medagent.safety.centor_strep_pharyngitis_scorer import (
    CentorStrepPharyngitisFactors,
    CentorStrepPharyngitisScorer,
)
from medagent.safety.gcs_neurologic_status_scorer import (
    GcsNeurologicStatusFactors,
    GcsNeurologicStatusScorer,
)
from medagent.safety.news2_early_warning_scorer import (
    News2EarlyWarningFactors,
    News2EarlyWarningScorer,
)
from medagent.safety.qsofa_sepsis_screen_scorer import (
    QSofaSepsisScreenFactors,
    QSofaSepsisScreenScorer,
)

INF = math.inf


def _evaluate_qsofa(values: Mapping[str, Any]) -> Evaluation:
    rr, sbp = values["respiratory_rate"], values["systolic_bp"]
    components = (
        threshold(
            "respiratory_rate_ge_22",
            "Respiratory rate >= 22/min",
            input_name="respiratory_rate",
            value=rr,
            unit="/min",
            met=rr >= 22,
            met_text=">= 22",
            unmet_text="< 22",
            points=1,
        ),
        flag(
            "altered_mentation",
            "Altered mentation (GCS < 15)",
            values["altered_mentation"],
            1,
            "altered_mentation",
        ),
        threshold(
            "systolic_bp_le_100",
            "Systolic BP <= 100 mmHg",
            input_name="systolic_bp",
            value=sbp,
            unit="mmHg",
            met=sbp <= 100,
            met_text="<= 100",
            unmet_text="> 100",
            points=1,
        ),
    )
    fired = {c.criterion: int(c.earned > 0) for c in components}
    finding = QSofaSepsisScreenScorer().check(QSofaSepsisScreenFactors(**fired))[0]
    score = checked_total("qsofa", finding.score, components)
    return Evaluation(score, components, "positive" if score >= 2 else "negative")


QSOFA = Calculator(
    id="qsofa",
    name="qSOFA (quick Sequential Organ Failure Assessment)",
    version="1.0.0",
    category="critical care",
    purpose="Bedside prompt for adults with suspected infection at risk of poor outcomes.",
    inputs=(
        common.respiratory_rate(),
        common.systolic_bp(),
        common.boolean(
            "altered_mentation",
            "Altered mentation",
            "Any altered mentation (Glasgow Coma Scale < 15).",
        ),
    ),
    bands=(
        Band(
            "negative",
            "qSOFA < 2",
            "0-1",
            "Fewer than two criteria; does not exclude sepsis (Seymour 2016).",
            Severity.LOW,
        ),
        Band(
            "positive",
            "qSOFA >= 2",
            "2-3",
            "Outside the ICU, in-hospital mortality was 3- to 14-fold higher than with qSOFA < 2 "
            "across baseline-risk deciles (Seymour 2016).",
            Severity.HIGH,
        ),
    ),
    citations=(
        Citation(
            "Seymour CW, Liu VX, Iwashyna TJ, et al. Assessment of clinical criteria for sepsis: "
            "for the Third International Consensus Definitions for Sepsis and Septic Shock "
            "(Sepsis-3). JAMA. 2016;315(8):762-774.",
            doi="10.1001/jama.2016.0288",
            pmid="26903335",
        ),
    ),
    limitations=(
        "qSOFA is a prognostic prompt, not a diagnostic criterion for sepsis, and is not "
        "recommended as a single screening tool (Surviving Sepsis Campaign 2021).",
        "The wrapped QSofaSepsisScreenScorer labels one criterion 'moderate'; the calculator "
        "reports the published two-way interpretation.",
    ),
    evaluate=_evaluate_qsofa,
    score_range="0-3",
    wraps="QSofaSepsisScreenScorer",
)


_NEWS2_RR = ((8, 3, "<= 8"), (11, 1, "9-11"), (20, 0, "12-20"), (24, 2, "21-24"), (INF, 3, ">= 25"))
_NEWS2_SPO2_SCALE_1 = ((91, 3, "<= 91"), (93, 2, "92-93"), (95, 1, "94-95"), (INF, 0, ">= 96"))
_NEWS2_SPO2_SCALE_2_AIR = (
    (83, 3, "<= 83"),
    (85, 2, "84-85"),
    (87, 1, "86-87"),
    (INF, 0, ">= 88 on air"),
)
_NEWS2_SPO2_SCALE_2_O2 = (
    (83, 3, "<= 83"),
    (85, 2, "84-85"),
    (87, 1, "86-87"),
    (92, 0, "88-92"),
    (94, 1, "93-94 on oxygen"),
    (96, 2, "95-96 on oxygen"),
    (INF, 3, ">= 97 on oxygen"),
)
_NEWS2_SBP = (
    (90, 3, "<= 90"),
    (100, 2, "91-100"),
    (110, 1, "101-110"),
    (219, 0, "111-219"),
    (INF, 3, ">= 220"),
)
_NEWS2_HR = (
    (40, 3, "<= 40"),
    (50, 1, "41-50"),
    (90, 0, "51-90"),
    (110, 1, "91-110"),
    (130, 2, "111-130"),
    (INF, 3, ">= 131"),
)
_NEWS2_TEMP = (
    (35.0, 3, "<= 35.0"),
    (36.0, 1, "35.1-36.0"),
    (38.0, 0, "36.1-38.0"),
    (39.0, 1, "38.1-39.0"),
    (INF, 2, ">= 39.1"),
)


def _evaluate_news2(values: Mapping[str, Any]) -> Evaluation:
    on_oxygen = values["supplemental_oxygen"]
    scale_2 = values["spo2_scale"] == "scale_2"
    spo2_table = (
        (_NEWS2_SPO2_SCALE_2_O2 if on_oxygen else _NEWS2_SPO2_SCALE_2_AIR)
        if scale_2
        else _NEWS2_SPO2_SCALE_1
    )
    alert = values["consciousness"] == "alert"
    components = (
        banded(
            "respiration",
            "Respiration rate",
            input_name="respiratory_rate",
            value=values["respiratory_rate"],
            unit="/min",
            table=_NEWS2_RR,
        ),
        banded(
            "oxygen_sat",
            f"SpO2 ({'Scale 2' if scale_2 else 'Scale 1'})",
            input_name="oxygen_saturation",
            value=values["oxygen_saturation"],
            unit="%",
            table=spo2_table,
        ),
        flag("supplemental_o2", "Air or oxygen (oxygen +2)", on_oxygen, 2, "supplemental_oxygen"),
        banded(
            "systolic_bp",
            "Systolic blood pressure",
            input_name="systolic_bp",
            value=values["systolic_bp"],
            unit="mmHg",
            table=_NEWS2_SBP,
        ),
        banded(
            "heart_rate",
            "Pulse",
            input_name="heart_rate",
            value=values["heart_rate"],
            unit="/min",
            table=_NEWS2_HR,
        ),
        Criterion(
            "consciousness",
            "Consciousness (ACVPU: any new C, V, P or U +3)",
            0 if alert else 3,
            f"consciousness {values['consciousness']}: {'0' if alert else '+3'}",
            ("consciousness",),
        ),
        banded(
            "temperature",
            "Temperature",
            input_name="temperature",
            value=values["temperature"],
            unit="°C",
            table=_NEWS2_TEMP,
        ),
    )
    points = {c.criterion: int(c.earned) for c in components}
    finding = News2EarlyWarningScorer().check(News2EarlyWarningFactors(**points))[0]
    return Evaluation(checked_total("news2", finding.score, components), components, finding.band)


NEWS2 = Calculator(
    id="news2",
    name="NEWS2 (National Early Warning Score 2)",
    version="1.0.0",
    category="critical care",
    purpose="Aggregate track-and-trigger score of acute-illness severity in adults.",
    inputs=(
        common.respiratory_rate(),
        common.oxygen_saturation(),
        InputSpec(
            "spo2_scale",
            "SpO2 scale",
            "choice",
            "Scale 1 for most patients; Scale 2 only for hypercapnic respiratory failure with a "
            "prescribed target of 88-92%, as decided by a clinician.",
            choices=(
                Choice("scale_1", "Scale 1 (default)"),
                Choice("scale_2", "Scale 2 (target 88-92%)"),
            ),
            required=False,
            default="scale_1",
        ),
        common.boolean(
            "supplemental_oxygen", "Supplemental oxygen", "Breathing supplemental oxygen (not air)."
        ),
        common.systolic_bp(),
        common.heart_rate(),
        InputSpec(
            "consciousness",
            "Consciousness (ACVPU)",
            "choice",
            "Alert, or new Confusion, responds to Voice, responds to Pain, Unresponsive.",
            choices=(
                Choice("alert", "Alert (0)"),
                Choice("new_confusion", "New confusion (+3)"),
                Choice("voice", "Responds to voice (+3)"),
                Choice("pain", "Responds to pain (+3)"),
                Choice("unresponsive", "Unresponsive (+3)"),
            ),
        ),
        common.temperature(),
    ),
    bands=(
        Band(
            "low",
            "Low clinical risk",
            "0-4",
            "Aggregate 0-4 with no single parameter scoring 3.",
            Severity.LOW,
        ),
        Band(
            "low_medium",
            "Low-medium clinical risk",
            "red score",
            "A single parameter scores 3 (red score) with an aggregate of 0-4; RCP 2017 asks for "
            "an urgent ward-based response.",
            Severity.MODERATE,
        ),
        Band(
            "moderate",
            "Medium clinical risk",
            "5-6",
            "Aggregate 5-6 (key threshold for urgent response).",
            Severity.MODERATE,
        ),
        Band(
            "high",
            "High clinical risk",
            "7-20",
            "Aggregate 7 or more (emergency response threshold).",
            Severity.HIGH,
        ),
    ),
    citations=(
        Citation(
            "Royal College of Physicians. National Early Warning Score (NEWS) 2: Standardising "
            "the assessment of acute-illness severity in the NHS. Updated report of a working "
            "party. London: RCP, 2017.",
            url="https://www.rcp.ac.uk/resources/national-early-warning-score-news-2/",
        ),
    ),
    limitations=(
        "Not validated for children (< 16 years) or pregnancy.",
        "SpO2 Scale 2 must only be used when a clinician has prescribed a target of 88-92%; "
        "spo2_scale defaults to Scale 1 and the result names the scale used.",
        "A single observation set; NEWS2 is designed for repeated observations and trends.",
    ),
    evaluate=_evaluate_news2,
    score_range="0-20",
    wraps="News2EarlyWarningScorer",
)


def _evaluate_gcs(values: Mapping[str, Any]) -> Evaluation:
    eye, verbal, motor = values["eye"], values["verbal"], values["motor"]
    components = (
        Criterion("eye", "Eye opening (1-4)", eye, f"eye {eye}: +{eye}", ("eye",)),
        Criterion(
            "verbal", "Verbal response (1-5)", verbal, f"verbal {verbal}: +{verbal}", ("verbal",)
        ),
        Criterion("motor", "Motor response (1-6)", motor, f"motor {motor}: +{motor}", ("motor",)),
    )
    factors = GcsNeurologicStatusFactors(eye_points=eye, verbal_points=verbal, motor_points=motor)
    finding = GcsNeurologicStatusScorer().check(factors)[0]
    return Evaluation(checked_total("gcs", finding.score, components), components, finding.band)


GCS = Calculator(
    id="gcs",
    name="Glasgow Coma Scale",
    version="1.0.0",
    category="neurology",
    purpose="Level of consciousness from eye, verbal and motor responses.",
    inputs=(
        InputSpec(
            "eye",
            "Eye opening",
            "integer",
            "4 spontaneous, 3 to sound, 2 to pressure/pain, 1 none.",
            minimum=1,
            maximum=4,
        ),
        InputSpec(
            "verbal",
            "Verbal response",
            "integer",
            "5 oriented, 4 confused, 3 words, 2 sounds, 1 none.",
            minimum=1,
            maximum=5,
        ),
        InputSpec(
            "motor",
            "Motor response",
            "integer",
            "6 obeys commands, 5 localising, 4 normal flexion/withdrawal, 3 abnormal flexion, "
            "2 extension, 1 none.",
            minimum=1,
            maximum=6,
        ),
    ),
    bands=(
        Band(
            "severe",
            "Severe impairment",
            "3-8",
            "Conventional severe band (GCS <= 8).",
            Severity.HIGH,
        ),
        Band(
            "moderate",
            "Moderate impairment",
            "9-12",
            "Conventional moderate band.",
            Severity.MODERATE,
        ),
        Band("mild", "Mild or no impairment", "13-15", "Conventional mild band.", Severity.LOW),
    ),
    citations=(
        Citation(
            "Teasdale G, Jennett B. Assessment of coma and impaired consciousness. A practical "
            "scale. Lancet. 1974;2(7872):81-84.",
            doi="10.1016/S0140-6736(74)91639-0",
            pmid="4136544",
        ),
    ),
    limitations=(
        "The mild/moderate/severe bands are the conventional head-injury classification, not "
        "part of the 1974 scale; report the three components, not only the total.",
        "Untestable components (intubation, eye swelling, aphasia) cannot be scored here; the "
        "caller must not substitute a guessed value.",
    ),
    evaluate=_evaluate_gcs,
    score_range="3-15",
    wraps="GcsNeurologicStatusScorer",
)


def _evaluate_centor(values: Mapping[str, Any]) -> Evaluation:
    age, temperature = values["age"], values["temperature"]
    age_points = 1 if age <= 14 else 0 if age <= 44 else -1
    age_text = "3-14" if age <= 14 else "15-44" if age <= 44 else ">= 45"
    components = (
        threshold(
            "fever_history",
            "Temperature > 38 °C",
            input_name="temperature",
            value=temperature,
            unit="°C",
            met=temperature > 38.0,
            met_text="> 38",
            unmet_text="<= 38",
            points=1,
        ),
        flag("cough_absent", "Absence of cough", values["cough_absent"], 1, "cough_absent"),
        flag(
            "tender_anterior_nodes",
            "Swollen, tender anterior cervical nodes",
            values["tender_anterior_cervical_nodes"],
            1,
            "tender_anterior_cervical_nodes",
        ),
        flag(
            "tonsillar_exudate",
            "Tonsillar swelling or exudate",
            values["tonsillar_swelling_or_exudate"],
            1,
            "tonsillar_swelling_or_exudate",
        ),
        Criterion(
            "age_bonus",
            "Age 3-14 (+1), 15-44 (0), >= 45 years (-1)",
            age_points,
            f"age {age} years in {age_text}: {'+1' if age_points > 0 else age_points}",
            ("age",),
        ),
    )
    points = {c.criterion: int(c.earned) for c in components}
    finding = CentorStrepPharyngitisScorer().check(CentorStrepPharyngitisFactors(**points))[0]
    return Evaluation(
        checked_total("centor_mcisaac", finding.score, components), components, finding.band
    )


CENTOR_MCISAAC = Calculator(
    id="centor_mcisaac",
    name="Centor score, McIsaac modification (streptococcal pharyngitis)",
    version="1.0.0",
    category="infectious disease",
    purpose="Likelihood of group A streptococcal pharyngitis in patients with a sore throat.",
    inputs=(
        common.age(3, description="Age in completed years (validated from 3 years)."),
        common.temperature("Highest measured temperature."),
        common.boolean("cough_absent", "Cough absent", "Absence of cough."),
        common.boolean(
            "tender_anterior_cervical_nodes",
            "Tender anterior cervical nodes",
            "Swollen, tender anterior cervical lymph nodes.",
        ),
        common.boolean(
            "tonsillar_swelling_or_exudate",
            "Tonsillar swelling or exudate",
            "Tonsillar swelling or exudate.",
        ),
    ),
    bands=(
        Band(
            "low",
            "Low likelihood",
            "-1 to 1",
            "Lowest likelihood strata of group A streptococcal infection (McIsaac 1998).",
            Severity.LOW,
        ),
        Band(
            "moderate",
            "Intermediate likelihood",
            "2-3",
            "Intermediate likelihood strata (McIsaac 1998).",
            Severity.MODERATE,
        ),
        Band(
            "high",
            "High likelihood",
            "4-5",
            "Highest likelihood strata of group A streptococcal infection (McIsaac 1998).",
            Severity.HIGH,
        ),
    ),
    citations=(
        Citation(
            "McIsaac WJ, White D, Tannenbaum D, Low DE. A clinical score to reduce unnecessary "
            "antibiotic use in patients with sore throat. CMAJ. 1998;158(1):75-83.",
            pmid="9475915",
        ),
        Citation(
            "McIsaac WJ, Kellner JD, Aufricht P, Vanjaka A, Low DE. Empirical validation of "
            "guidelines for the management of pharyngitis in children and adults. JAMA. "
            "2004;291(13):1587-1595.",
            doi="10.1001/jama.291.13.1587",
            pmid="15069046",
        ),
    ),
    limitations=(
        "Temperature uses the measured value (> 38 °C); a reported history of fever without a "
        "measurement must be judged by the clinician.",
        "Not validated below age 3; the score estimates likelihood and does not replace a "
        "rapid antigen test or culture.",
    ),
    evaluate=_evaluate_centor,
    score_range="-1 to 5",
    wraps="CentorStrepPharyngitisScorer",
)
