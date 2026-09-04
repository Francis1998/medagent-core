"""Core Pydantic domain models shared across the entire medagent-core package.

All models are immutable by default (frozen=True) to prevent accidental
in-place mutation of clinical data flowing through the pipeline.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class AgentState(str, Enum):
    """Finite states of the clinical reasoning agent."""

    INTAKE = "INTAKE"
    ENTITY_EXTRACTION = "ENTITY_EXTRACTION"
    KNOWLEDGE_RETRIEVAL = "KNOWLEDGE_RETRIEVAL"
    REASONING = "REASONING"
    SAFETY_CHECK = "SAFETY_CHECK"
    OUTPUT = "OUTPUT"
    ESCALATE = "ESCALATE"
    ERROR = "ERROR"


class Severity(str, Enum):
    """Clinical severity classification."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class HepaticFunction(str, Enum):
    """Hepatic-function class used for hepatic dose adjustment.

    Ordered by increasing impairment, mirroring the Child-Pugh classification:
    ``MILD`` corresponds to Child-Pugh A, ``MODERATE`` to Child-Pugh B, and
    ``SEVERE`` to Child-Pugh C (decompensated cirrhosis). ``NORMAL`` denotes no
    clinically significant hepatic impairment.
    """

    NORMAL = "NORMAL"
    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"


class LLMProvider(str, Enum):
    """Supported LLM backend providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    KIMI = "kimi"


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class LabResult(BaseModel, frozen=True):
    """A single laboratory test result."""

    test_name: str
    value: str
    unit: str | None = None
    reference_range: str | None = None
    abnormal: bool = False


class Medication(BaseModel, frozen=True):
    """A medication entry with optional dosage metadata."""

    name: str
    rxnorm_code: str | None = None
    dosage: str | None = None
    route: str | None = None
    frequency: str | None = None


class FHIRPatientContext(BaseModel, frozen=True):
    """Structured FHIR-compatible patient context.

    Patient-identifying fields are stored as hashes; the raw values are never
    persisted beyond the intake boundary. See ``src/medagent/safety/pii_hasher.py``.
    """

    patient_id_hash: str = Field(description="SHA-256 hash of the original patient MRN/ID")
    age: int | None = Field(default=None, ge=0, le=150)
    sex: str | None = Field(default=None, description="Biological sex for clinical context")
    chief_complaint: str = Field(description="Presenting complaint in free text")
    clinical_notes: str = Field(default="", description="Unstructured clinician notes")
    diagnoses_history: list[str] = Field(default_factory=list)
    medications: list[Medication] = Field(default_factory=list)
    lab_results: list[LabResult] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    raw_fhir: dict[str, Any] | None = Field(
        default=None,
        description="Original FHIR bundle — stored for audit, not passed to LLMs",
    )


class ClinicalQuery(BaseModel, frozen=True):
    """Top-level agent input combining FHIR context and a free-text question."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    patient_context: FHIRPatientContext
    query: str = Field(description="Clinician's question or reasoning task")
    requested_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def inputs_hash(self) -> str:
        """SHA-256 of patient_id_hash + query for audit trail deduplication."""
        payload = f"{self.patient_context.patient_id_hash}|{self.query}"
        return hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Intermediate reasoning models
# ---------------------------------------------------------------------------


class ClinicalEntity(BaseModel, frozen=True):
    """A biomedical entity extracted from clinical text."""

    text: str
    label: str = Field(description="Entity type e.g. DISEASE, CHEMICAL, GENE")
    start_char: int | None = None
    end_char: int | None = None
    cui: str | None = Field(default=None, description="UMLS Concept Unique Identifier")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class RetrievedDocument(BaseModel, frozen=True):
    """A document retrieved from an external knowledge source."""

    source: str = Field(description="e.g. 'pubmed', 'openfda', 'local_kb'")
    doc_id: str
    title: str
    snippet: str
    url: str | None = None
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    mesh_terms: list[str] = Field(default_factory=list)
    published_date: str | None = None


class EvidenceItem(BaseModel, frozen=True):
    """A single piece of evidence for or against a hypothesis."""

    direction: str = Field(description="'FOR' or 'AGAINST'")
    statement: str
    source_doc_id: str | None = None
    source_label: str | None = None
    strength: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("direction")
    @classmethod
    def direction_must_be_valid(cls, v: str) -> str:
        """Ensure direction is exactly FOR or AGAINST."""
        if v not in {"FOR", "AGAINST"}:
            raise ValueError("direction must be 'FOR' or 'AGAINST'")
        return v


class Hypothesis(BaseModel, frozen=True):
    """A candidate diagnosis or clinical hypothesis with evidence chain."""

    label: str = Field(description="Human-readable diagnosis or hypothesis name")
    icd_code: str | None = Field(default=None, description="ICD-10 code if available")
    evidence_for: list[EvidenceItem] = Field(default_factory=list)
    evidence_against: list[EvidenceItem] = Field(default_factory=list)
    bayesian_score: float = Field(default=0.0, ge=0.0, le=1.0)
    rank: int = Field(default=1, ge=1)
    uncertainty_note: str | None = None


class DrugInteractionWarning(BaseModel, frozen=True):
    """A validated drug-drug or drug-condition interaction warning."""

    drug_a: str
    drug_b: str
    severity: Severity
    mechanism: str
    clinical_consequence: str
    sources: list[str] = Field(description="At least 2 source identifiers required")
    validated: bool = Field(
        default=False,
        description="True only when confirmed by ≥2 independent data sources",
    )

    @field_validator("sources")
    @classmethod
    def require_multiple_sources(cls, v: list[str]) -> list[str]:
        """Enforce the triple-validation safety invariant at model construction time."""
        if len(v) < 2:
            raise ValueError("Drug interaction warnings require ≥2 independent sources")
        return v


class AllergyConflict(BaseModel, frozen=True):
    """A conflict between a prescribed medication and a documented allergy."""

    medication: str
    allergy: str
    match_type: str = Field(description="'direct' or 'cross_reactivity'")
    drug_class: str | None = Field(
        default=None, description="Shared drug class for cross-reactivity matches"
    )
    severity: Severity
    rationale: str

    @field_validator("match_type")
    @classmethod
    def match_type_must_be_valid(cls, v: str) -> str:
        """Ensure match_type is exactly 'direct' or 'cross_reactivity'."""
        if v not in {"direct", "cross_reactivity"}:
            raise ValueError("match_type must be 'direct' or 'cross_reactivity'")
        return v


class DuplicateTherapy(BaseModel, frozen=True):
    """Multiple active medications that share one therapeutic class."""

    therapeutic_class: str
    medications: list[str] = Field(
        description="Active medications sharing the therapeutic class (≥2 distinct agents)"
    )
    severity: Severity
    rationale: str

    @field_validator("medications")
    @classmethod
    def require_at_least_two(cls, v: list[str]) -> list[str]:
        """Enforce that a duplicate-therapy finding names at least two agents."""
        if len(v) < 2:
            raise ValueError("duplicate therapy requires at least two medications")
        return v


class PregnancyRisk(BaseModel, frozen=True):
    """A medication flagged as unsafe for use during pregnancy."""

    medication: str
    agent: str = Field(description="Canonical teratogenic agent matched in the medication name")
    severity: Severity
    rationale: str


class LactationRisk(BaseModel, frozen=True):
    """A medication flagged as a breastfeeding/lactation safety concern."""

    medication: str
    agent: str = Field(
        description="Canonical lactation-concern agent matched in the medication name"
    )
    concern_category: str = Field(
        description="Lactation concern category, such as antineoplastic or infant sedation risk"
    )
    severity: Severity
    rationale: str


class PregnancyLactationConcernKind(str, Enum):
    """Whether a finding reflects pregnancy-only, lactation-only, or dual concern."""

    COMBINED = "combined"
    PREGNANCY_ONLY = "pregnancy_only"
    LACTATION_ONLY = "lactation_only"


class PregnancyLactationRisk(BaseModel, frozen=True):
    """A medication with pregnancy and/or lactation safety concerns.

    Distinct from standalone :class:`PregnancyRisk` and :class:`LactationRisk`:
    this model unifies both hazard domains and escalates severity when the same
    medication triggers both pregnancy and lactation panels.
    """

    medication: str
    agent: str = Field(description="Canonical agent matched in the medication name for reporting")
    concern_kind: PregnancyLactationConcernKind = Field(
        description="Whether the finding is combined, pregnancy-only, or lactation-only"
    )
    pregnancy_severity: Severity | None = Field(
        default=None,
        description="Severity from the pregnancy component, when applicable",
    )
    lactation_severity: Severity | None = Field(
        default=None,
        description="Severity from the lactation component, when applicable",
    )
    lactation_concern_category: str | None = Field(
        default=None,
        description="Lactation concern category when the lactation component fired",
    )
    severity: Severity = Field(
        description="Overall severity, escalated for combined pregnancy+lactation concerns"
    )
    rationale: str


class RenalHepaticLactationConcernKind(str, Enum):
    """Whether a finding reflects organ-only, lactation-only, or dual concern."""

    COMBINED = "combined"
    ORGAN_ONLY = "organ_only"
    LACTATION_ONLY = "lactation_only"


class RenalHepaticLactationRisk(BaseModel, frozen=True):
    """A medication with organ-impairment and/or lactation safety concerns.

    Distinct from :class:`CombinedRenalHepaticRisk` and :class:`LactationRisk`:
    this model unifies renal-dose, hepatic-dose, and breastfeeding hazard domains
    and escalates severity when the same medication triggers organ impairment
    and lactation panels.
    """

    medication: str
    agent: str = Field(description="Canonical agent matched in the medication name for reporting")
    concern_kind: RenalHepaticLactationConcernKind = Field(
        description="Whether the finding is combined, organ-only, or lactation-only"
    )
    egfr: float | None = Field(
        default=None,
        description="Patient eGFR in mL/min/1.73m^2 when the renal component fired",
    )
    threshold_egfr: float | None = Field(
        default=None,
        description="eGFR threshold at or below which the renal component is flagged",
    )
    hepatic_function: HepaticFunction | None = Field(
        default=None,
        description="Patient Child-Pugh class when the hepatic component fired",
    )
    threshold_function: HepaticFunction | None = Field(
        default=None,
        description="Hepatic-function class at or above which the hepatic component is flagged",
    )
    renal_action: str | None = Field(
        default=None,
        description="Recommended action from the renal component, when applicable",
    )
    hepatic_action: str | None = Field(
        default=None,
        description="Recommended action from the hepatic component, when applicable",
    )
    renal_severity: Severity | None = Field(
        default=None,
        description="Severity from the renal component, when applicable",
    )
    hepatic_severity: Severity | None = Field(
        default=None,
        description="Severity from the hepatic component, when applicable",
    )
    organ_severity: Severity | None = Field(
        default=None,
        description="Maximum severity across renal and hepatic components that fired",
    )
    lactation_severity: Severity | None = Field(
        default=None,
        description="Severity from the lactation component, when applicable",
    )
    lactation_concern_category: str | None = Field(
        default=None,
        description="Lactation concern category when the lactation component fired",
    )
    severity: Severity = Field(
        description="Overall severity, escalated for combined organ+lactation concerns"
    )
    rationale: str


class FallRiskFinding(BaseModel, frozen=True):
    """A medication flagged for increased fall risk in older adults."""

    medication: str
    agent: str = Field(description="Canonical fall-risk agent matched in the medication name")
    risk_category: str = Field(
        description=(
            "Fall-risk category such as benzodiazepine, z-drug, anticholinergic, "
            "antipsychotic, or muscle relaxant"
        )
    )
    severity: Severity
    patient_age: int = Field(ge=0, description="Patient age in years used for the age gate")
    rationale: str


class QTProlongationRisk(BaseModel, frozen=True):
    """A medication that prolongs the QT interval (torsades-de-pointes risk)."""

    medication: str
    agent: str = Field(description="Canonical QT-prolonging agent matched in the medication name")
    severity: Severity
    concurrent_qt_medications: int = Field(
        default=0,
        ge=0,
        description="Count of other active QT-prolonging medications co-prescribed",
    )
    rationale: str


class QtcDdiRisk(BaseModel, frozen=True):
    """A known high-risk QTc-prolonging drug-drug interaction pair.

    Complements :class:`QTProlongationRisk`, which counts additive exposure to
    QT-prolonging agents. This model records named pairs with documented
    synergistic torsades risk.
    """

    medication_a: str = Field(description="First active medication in the matched pair")
    medication_b: str = Field(description="Second active medication in the matched pair")
    agent_a: str = Field(description="Canonical QTc-DDI panel agent matched in medication_a")
    agent_b: str = Field(description="Canonical QTc-DDI panel agent matched in medication_b")
    pair_id: str = Field(description="Stable curated-panel identifier for the interaction pair")
    severity: Severity
    mechanism: str = Field(description="Mechanism driving the synergistic QTc/torsades risk")
    clinical_consequence: str = Field(
        description="Expected clinical hazard, e.g. torsades de pointes or serious arrhythmia"
    )
    rationale: str


class QtcMonitoringRisk(BaseModel, frozen=True):
    """Inadequate ECG monitoring interval for a high-risk QT-prolonging medication.

    Complements :class:`QTProlongationRisk` and :class:`QtcDdiRisk` by flagging
    when periodic QTc/ECG surveillance is missing or overdue for agents that
    require close monitoring at initiation or during maintenance therapy.
    """

    medication: str
    agent: str = Field(description="Canonical high-risk QT agent matched in the medication name")
    risk_category: str = Field(
        description=(
            "High-risk QT category such as class III antiarrhythmic, opioid, "
            "antipsychotic, or SSRI (high dose)"
        )
    )
    severity: Severity
    last_ecg_days_ago: int | None = Field(
        default=None,
        ge=0,
        description="Days since the most recent ECG, or None when unknown/missing",
    )
    recommended_interval_days: int = Field(
        ge=1,
        description="Recommended maximum days between ECGs for the monitoring phase",
    )
    monitoring_phase: str = Field(
        description="Monitoring phase applied: 'initiation' (≤7 days) or 'maintenance' (≤30 days)"
    )
    baseline_qtc_ms: float | None = Field(
        default=None,
        ge=0,
        description="Most recent documented QTc interval in milliseconds, if known",
    )
    rationale: str

    @field_validator("monitoring_phase")
    @classmethod
    def monitoring_phase_must_be_valid(cls, v: str) -> str:
        """Ensure monitoring_phase is initiation or maintenance."""
        if v not in {"initiation", "maintenance"}:
            raise ValueError("monitoring_phase must be 'initiation' or 'maintenance'")
        return v


class AnticoagBleedingRisk(BaseModel, frozen=True):
    """An anticoagulant combined with an agent that elevates bleeding risk.

    Complements duplicate-therapy anticoagulant detection and generic DDI
    screening by flagging named anticoagulant × antiplatelet/NSAID/SSRI
    combinations with additive hemorrhagic hazard.
    """

    medication_a: str = Field(description="Active medication entry for the anticoagulant")
    medication_b: str = Field(description="Active medication entry for the bleeding-risk augmenter")
    anticoagulant_agent: str = Field(
        description="Canonical anticoagulant agent matched in medication_a"
    )
    augmenter_agent: str = Field(description="Canonical augmenter agent matched in medication_b")
    augmenter_category: str = Field(description="Augmenter category: antiplatelet, NSAID, or SSRI")
    combination_id: str = Field(
        description="Stable curated-panel identifier for the anticoagulant × augmenter pair"
    )
    severity: Severity
    mechanism: str = Field(description="Mechanism driving the additive bleeding risk")
    clinical_consequence: str = Field(
        description="Expected clinical hazard, e.g. major GI or intracranial hemorrhage"
    )
    rationale: str


class InrTtrRisk(BaseModel, frozen=True):
    """Inadequate INR monitoring cadence or suboptimal TTR for a VKA patient.

    Complements anticoagulation bleeding-risk checking and lab critical-value
    INR panic thresholds by flagging when warfarin/VKA therapy lacks timely INR
    surveillance or has time-in-therapeutic-range below a quality threshold.
    """

    medication: str
    agent: str = Field(description="Canonical vitamin K antagonist matched in the medication name")
    risk_category: str = Field(
        description="VKA risk category such as vitamin K antagonist (warfarin)"
    )
    finding_kind: str = Field(
        description=(
            "Finding kind: 'overdue_inr' when INR is missing/late, or "
            "'low_ttr' when TTR is below threshold"
        )
    )
    severity: Severity
    last_inr_days_ago: int | None = Field(
        default=None,
        ge=0,
        description="Days since the most recent INR, or None when unknown/missing",
    )
    recommended_interval_days: int | None = Field(
        default=None,
        ge=1,
        description="Recommended maximum days between INR checks for the monitoring phase",
    )
    monitoring_phase: str | None = Field(
        default=None,
        description="Monitoring phase applied: 'initiation' (≤7 days) or 'maintenance' (≤28 days)",
    )
    ttr_percent: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Documented time in therapeutic range as a percentage, if known",
    )
    ttr_threshold_percent: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="TTR percentage threshold used for the low_ttr finding",
    )
    rationale: str

    @field_validator("finding_kind")
    @classmethod
    def finding_kind_must_be_valid(cls, v: str) -> str:
        """Ensure finding_kind is overdue_inr or low_ttr."""
        if v not in {"overdue_inr", "low_ttr"}:
            raise ValueError("finding_kind must be 'overdue_inr' or 'low_ttr'")
        return v

    @field_validator("monitoring_phase")
    @classmethod
    def monitoring_phase_must_be_valid(cls, v: str | None) -> str | None:
        """Ensure monitoring_phase is initiation, maintenance, or omitted."""
        if v is not None and v not in {"initiation", "maintenance"}:
            raise ValueError("monitoring_phase must be 'initiation' or 'maintenance'")
        return v


class AnticholinergicBurdenRisk(BaseModel, frozen=True):
    """A medication contributing to cumulative anticholinergic burden."""

    medication: str
    agent: str = Field(description="Canonical anticholinergic agent matched in the medication name")
    anticholinergic_score: int = Field(
        ge=1,
        le=3,
        description="Anticholinergic Cognitive Burden (ACB) score contributed by this agent (1-3)",
    )
    total_burden: int = Field(
        ge=1,
        description="Sum of ACB scores across all active anticholinergic medications",
    )
    severity: Severity
    rationale: str


class SerotoninSyndromeRisk(BaseModel, frozen=True):
    """A serotonergic medication contributing to serotonin-syndrome risk."""

    medication: str
    agent: str = Field(description="Canonical serotonergic agent matched in the medication name")
    drug_class: str = Field(description="Serotonergic drug class (e.g. SSRI, SNRI, MAOI, triptan)")
    concurrent_serotonergic_medications: int = Field(
        default=0,
        ge=0,
        description="Count of other active serotonergic medications co-prescribed",
    )
    severity: Severity
    rationale: str


class BeersCriteriaRisk(BaseModel, frozen=True):
    """A potentially inappropriate medication (PIM) for an older adult.

    Based on the American Geriatrics Society (AGS) Beers Criteria, which flag
    medications whose risk generally outweighs their benefit in adults aged 65
    and older.
    """

    medication: str
    agent: str = Field(description="Canonical Beers-listed agent matched in the medication name")
    beers_category: str = Field(
        description="Beers Criteria category (e.g. 'long-acting benzodiazepine')"
    )
    severity: Severity
    rationale: str


class Beers2023DeltaRisk(BaseModel, frozen=True):
    """A 2023 AGS Beers Criteria update delta for an older adult.

    Complements :class:`BeersCriteriaRisk` by focusing on medications newly
    added or strengthened as avoid/caution recommendations in the 2023 update
    relative to the prior Beers edition, rather than reproducing the full
    classic PIM panel.
    """

    medication: str
    agent: str = Field(
        description="Canonical 2023-delta Beers agent matched in the medication name"
    )
    delta_kind: str = Field(
        description=(
            "Update kind: 'new_avoid', 'new_caution', 'expanded_avoid', or 'concurrent_avoid'"
        )
    )
    beers_category: str = Field(
        description="Beers category for the 2023 delta (e.g. 'sulfonylurea', 'SNRI')"
    )
    update_summary: str = Field(
        description="Short description of what changed versus the prior Beers edition"
    )
    severity: Severity
    patient_age: int = Field(ge=0, description="Patient age in years used for the age gate")
    medication_b: str | None = Field(
        default=None,
        description="Second medication when the delta is a concurrent-use pair, else None",
    )
    agent_b: str | None = Field(
        default=None,
        description="Second canonical agent when the delta is a concurrent-use pair, else None",
    )
    rationale: str

    @field_validator("delta_kind")
    @classmethod
    def delta_kind_must_be_valid(cls, v: str) -> str:
        """Ensure delta_kind is one of the curated 2023 update kinds."""
        allowed = {"new_avoid", "new_caution", "expanded_avoid", "concurrent_avoid"}
        if v not in allowed:
            raise ValueError(f"delta_kind must be one of {sorted(allowed)}")
        return v


class GeriatricDeprescribingRisk(BaseModel, frozen=True):
    """A medication that may be a geriatric deprescribing opportunity.

    Complements Beers and STOPP/START by focusing on review/taper candidates
    commonly targeted during older-adult medication reconciliation, rather than
    reproducing formal potentially-inappropriate-medication criteria.
    """

    medication: str
    agent: str = Field(
        description="Canonical deprescribing-panel agent matched in the medication name"
    )
    deprescribing_category: str = Field(
        description="Opportunity category (e.g. 'long-term PPI without clear indication')"
    )
    suggested_action: str = Field(
        description="Research-only deprescribing review action, such as taper or step-down"
    )
    taper_candidate: bool = Field(
        description="Whether abrupt discontinuation should generally be avoided in chronic use"
    )
    severity: Severity
    rationale: str


class TaperScheduleRisk(BaseModel, frozen=True):
    """A medication that may warrant taper-schedule review.

    This advisory model is intentionally not a taper prescription. It records
    conservative, research-only opportunities where abrupt discontinuation can
    cause withdrawal, rebound symptoms, relapse, or avoidable distress unless a
    qualified clinician designs and supervises an individualized taper plan.
    """

    medication: str
    agent: str = Field(description="Canonical taper-panel agent matched in the medication name")
    medication_class: str = Field(
        description="Curated class: opioid, benzodiazepine_z_drug, ppi, ssri, or snri"
    )
    taper_opportunity: str = Field(
        description="Research-only taper opportunity category for the matched medication"
    )
    suggested_review: str = Field(
        description="Non-prescriptive clinician review action; never a patient-specific taper"
    )
    abrupt_stop_concern: str = Field(
        description="Why abrupt discontinuation may be unsafe or poorly tolerated"
    )
    taper_candidate: bool = Field(
        description=(
            "Whether the medication generally requires gradual clinician-supervised tapering"
        )
    )
    severity: Severity
    rationale: str

    @field_validator("medication_class")
    @classmethod
    def medication_class_must_be_valid(cls, v: str) -> str:
        """Ensure medication_class is one of the supported taper panel classes."""
        allowed = {"opioid", "benzodiazepine_z_drug", "ppi", "ssri", "snri"}
        if v not in allowed:
            raise ValueError("medication_class must be a supported taper panel class")
        return v


class RenalDoseRisk(BaseModel, frozen=True):
    """A renally-cleared medication flagged against a patient's kidney function.

    Based on renal-function (eGFR) thresholds below which a medication is
    contraindicated or requires dose adjustment because reduced clearance leads
    to accumulation and toxicity.
    """

    medication: str
    agent: str = Field(description="Canonical renally-cleared agent matched in the medication name")
    egfr: float = Field(description="Patient eGFR in mL/min/1.73m^2 used for the assessment")
    threshold_egfr: float = Field(
        description="eGFR threshold at or below which the medication is flagged"
    )
    action: str = Field(description="Recommended action (e.g. 'avoid', 'reduce dose')")
    severity: Severity
    rationale: str


class HepaticDoseRisk(BaseModel, frozen=True):
    """A hepatically-cleared or hepatotoxic medication flagged against liver function.

    Based on hepatic-function (Child-Pugh) thresholds at or above which a
    medication is contraindicated or requires dose adjustment because impaired
    hepatic metabolism, hepatotoxicity, or a heightened risk of bleeding or
    encephalopathy makes continued use hazardous.
    """

    medication: str
    agent: str = Field(description="Canonical hepatic agent matched in the medication name")
    hepatic_function: HepaticFunction = Field(
        description="Patient hepatic-function class used for the assessment"
    )
    threshold_function: HepaticFunction = Field(
        description="Hepatic-function class at or above which the medication is flagged"
    )
    action: str = Field(description="Recommended action (e.g. 'avoid', 'reduce dose')")
    severity: Severity
    rationale: str


class CombinedRenalHepaticRisk(BaseModel, frozen=True):
    """A medication with concurrent renal and hepatic impairment concerns.

    Distinct from the individual renal-dose and hepatic-dose risks: this hazard
    surfaces only when the same active medication and canonical agent triggers
    both organ-function checkers for the same patient context.
    """

    medication: str
    agent: str = Field(description="Canonical agent matched by both component checkers")
    egfr: float = Field(description="Patient eGFR in mL/min/1.73m^2 used for renal assessment")
    threshold_egfr: float = Field(
        description="eGFR threshold at or below which the renal component is flagged"
    )
    hepatic_function: HepaticFunction = Field(
        description="Patient hepatic-function class used for hepatic assessment"
    )
    threshold_function: HepaticFunction = Field(
        description="Hepatic-function class at or above which the hepatic component is flagged"
    )
    renal_action: str = Field(description="Recommended action from the renal component")
    hepatic_action: str = Field(description="Recommended action from the hepatic component")
    renal_severity: Severity = Field(description="Severity assigned by the renal component")
    hepatic_severity: Severity = Field(description="Severity assigned by the hepatic component")
    severity: Severity = Field(description="Maximum severity of the renal and hepatic components")
    rationale: str


class LabCriticalValueRisk(BaseModel, frozen=True):
    """A laboratory result whose value crosses a critical (panic) threshold.

    Independent of any medication, a lab value at or beyond a standardized
    critical (panic) threshold — for example potassium >6.0 mmol/L or glucose
    <40 mg/dL — signals a potentially life-threatening state that warrants
    urgent clinician notification, so it is not surfaced by the medication-keyed
    checkers.
    """

    test_name: str = Field(description="Reported laboratory test name as received")
    canonical_test: str = Field(description="Canonical panel test the result matched")
    value: float = Field(description="Parsed numeric result value")
    unit: str | None = Field(default=None, description="Result unit when reported")
    direction: str = Field(description="Whether the value is 'critically low' or 'critically high'")
    threshold: float = Field(description="Critical threshold the value crossed")
    action: str = Field(description="Recommended action (e.g. 'urgent clinician notification')")
    severity: Severity
    rationale: str


class DrugFoodInteractionRisk(BaseModel, frozen=True):
    """A clinically significant interaction between a medication and a dietary exposure.

    Distinct from drug–drug interactions, allergies, and duplicate therapy: the
    hazard pairs an active medication with a food or beverage exposure (for
    example grapefruit with a statin, or tyramine with an MAOI).
    """

    medication: str
    agent: str = Field(description="Canonical interacting agent matched in the medication name")
    dietary_flag: str = Field(description="Reported dietary exposure flag as received")
    food_category: str = Field(
        description="Canonical food/beverage category (e.g. grapefruit, dairy, tyramine, alcohol)"
    )
    severity: Severity
    rationale: str


class OpioidMedRisk(BaseModel, frozen=True):
    """An opioid medication contributing to cumulative morphine-equivalent dose (MED).

    Distinct from duplicate-therapy (intra-class redundancy) and hepatic-dose
    (Child-Pugh) opioid flags: this hazard is a *dose-cumulative* judgement keyed
    on CDC-style oral morphine milligram equivalents (MME/MED). High total MED is
    associated with overdose and respiratory-depression risk.
    """

    medication: str
    agent: str = Field(description="Canonical opioid agent matched in the medication name")
    daily_dose: float = Field(
        description="Parsed daily dose in the agent's native unit (mg/day or mcg/hr for fentanyl)"
    )
    dose_unit: str = Field(description="Unit of daily_dose (e.g. 'mg/day', 'mcg/hr')")
    conversion_factor: float = Field(
        description="CDC-style MME conversion factor applied to this agent's daily dose"
    )
    med_contribution: float = Field(
        description="Morphine-equivalent dose (MED/MME) contributed by this medication"
    )
    total_med: float = Field(
        description="Sum of MED contributions across all active opioid medications"
    )
    high_med_threshold: float = Field(
        description="High-MED threshold used for severity elevation (default 90.0)"
    )
    severity: Severity
    rationale: str


class PediatricDoseRisk(BaseModel, frozen=True):
    """A paediatric age-contraindication or mg/kg daily-dose excess finding.

    Distinct from Beers (older-adult PIM), renal/hepatic dose, and pregnancy
    checkers: this hazard is an *age- and weight-conditioned* paediatric
    appropriateness judgement (for example codeine/tramadol under 12 years, or
    acetaminophen exceeding ~75 mg/kg/day).
    """

    medication: str
    agent: str = Field(
        description="Canonical paediatric-panel agent matched in the medication name"
    )
    age_years: float | None = Field(default=None, description="Patient age in years when known")
    weight_kg: float | None = Field(
        default=None, description="Patient weight in kilograms when known"
    )
    min_age_years: float | None = Field(
        default=None,
        description="Exclusive minimum age for the agent when the finding is age-gated",
    )
    dose_mg_per_kg_day: float | None = Field(
        default=None, description="Calculated total daily dose in mg/kg/day when parseable"
    )
    max_mg_per_kg_day: float | None = Field(
        default=None, description="Panel maximum total daily dose in mg/kg/day when applicable"
    )
    finding_kind: str = Field(
        description=(
            "Kind of paediatric finding: 'age_contraindication', 'mg_per_kg_excess', "
            "or 'age_and_mg_per_kg'"
        )
    )
    severity: Severity
    rationale: str


class StoppStartRisk(BaseModel, frozen=True):
    """A STOPP/START prescribing-criteria finding for an older adult.

    Complements Beers Criteria: STOPP flags medications that should usually be
    stopped (or avoided), while START flags indicated therapies that appear to
    be omitted given documented conditions. Applies to adults aged 65+.
    """

    medication: str | None = Field(
        default=None,
        description="Matched medication name for STOPP findings; None for START omissions",
    )
    agent: str = Field(
        description="Canonical agent matched (STOPP) or an example expected agent (START)"
    )
    criterion_id: str = Field(description="Stable criterion id (e.g. 'STOPP-D1', 'START-A5')")
    criterion_type: str = Field(description="Criterion family: 'STOPP' or 'START'")
    severity: Severity
    rationale: str


class BlackBoxWarningRisk(BaseModel, frozen=True):
    """An active medication that carries an FDA boxed (black-box) warning.

    Distinct from pregnancy, Beers, and interaction checkers: this hazard is a
    *labelling-severity* judgement keyed on agents whose US prescribing
    information includes an FDA boxed warning.
    """

    medication: str
    agent: str = Field(description="Canonical boxed-warning agent matched in the medication name")
    warning_theme: str = Field(
        description="Boxed-warning theme/class (e.g. 'fluoroquinolone', 'clozapine')"
    )
    severity: Severity
    rationale: str


class AntibioticStewardshipRisk(BaseModel, frozen=True):
    """An advisory antibiotic-stewardship safety finding.

    Flags high-risk antimicrobial-use patterns that are distinct from allergy,
    duplicate-therapy, QT, renal/hepatic dose, STOPP/START, and FDA boxed-warning
    hazards: broad fluoroquinolone use without a documented indication,
    duplicate antimicrobial coverage, and prolonged-course cues.
    """

    concern: str = Field(
        description=(
            "Stewardship concern kind: 'fluoroquinolone_without_indication', "
            "'duplicate_coverage', or 'prolonged_duration'"
        )
    )
    medications: list[str] = Field(
        description="Active antibiotic medication names involved in the finding"
    )
    agents: list[str] = Field(description="Canonical antibiotic agents matched")
    severity: Severity
    coverage_class: str | None = Field(
        default=None,
        description="Coverage class involved when duplicate antimicrobial coverage is flagged",
    )
    duration_days: float | None = Field(
        default=None,
        description="Parsed or inferred duration in days when prolonged-course cues are flagged",
    )
    indication_context: str | None = Field(
        default=None,
        description="Documented indication text used for fluoroquinolone stewardship checks",
    )
    rationale: str

    @field_validator("concern")
    @classmethod
    def concern_must_be_valid(cls, v: str) -> str:
        """Ensure concern is one of the supported stewardship finding types."""
        allowed = {
            "fluoroquinolone_without_indication",
            "duplicate_coverage",
            "prolonged_duration",
        }
        if v not in allowed:
            raise ValueError("concern must be a supported antibiotic-stewardship finding type")
        return v

    @field_validator("medications", "agents")
    @classmethod
    def require_non_empty_lists(cls, v: list[str]) -> list[str]:
        """Ensure stewardship findings always name at least one medication and agent."""
        if not v:
            raise ValueError("antibiotic stewardship findings require at least one entry")
        return v


class PediatricRenalRisk(BaseModel, frozen=True):
    """A pediatric renally-cleared medication with missing or inadequate renal function.

    Complements :class:`RenalDoseRisk` (adult eGFR-conditioned dosing) and
    :class:`PediatricDoseRisk` (age/weight contraindications) by flagging
    renally-cleared agents in patients under 18 when eGFR/CrCl is missing or
    below age-adjusted thresholds.
    """

    medication: str
    agent: str = Field(
        description="Canonical renally-cleared pediatric agent matched in the medication name"
    )
    finding_kind: str = Field(
        description=(
            "Finding kind: 'missing_renal_function' when eGFR and CrCl are absent, "
            "or 'below_renal_threshold' when renal function is below the age-adjusted threshold"
        )
    )
    severity: Severity
    age_years: float = Field(description="Patient age in years (pediatric, <18)")
    egfr: float | None = Field(
        default=None,
        description="Estimated GFR in mL/min/1.73m² when known",
    )
    crcl: float | None = Field(
        default=None,
        description="Creatinine clearance in mL/min when known",
    )
    age_adjusted_threshold: float = Field(
        description="Age-adjusted minimum acceptable eGFR/CrCl for the pediatric patient"
    )
    concern: str = Field(description="Clinical concern when renal function is inadequate")
    rationale: str

    @field_validator("finding_kind")
    @classmethod
    def finding_kind_must_be_valid(cls, v: str) -> str:
        """Ensure finding_kind is missing_renal_function or below_renal_threshold."""
        if v not in {"missing_renal_function", "below_renal_threshold"}:
            raise ValueError(
                "finding_kind must be 'missing_renal_function' or 'below_renal_threshold'"
            )
        return v


class MaoiSerotoninRisk(BaseModel, frozen=True):
    """An MAOI co-prescribed with a serotonergic medication.

    Complements :class:`SerotoninSyndromeRisk` (any two or more serotonergic
    agents) by providing a focused MAOI × serotonergic cross-check with explicit
    partner pairing. MAOI plus serotonergic combinations are contraindicated.
    """

    medication: str = Field(description="Medication name containing the matched MAOI")
    agent: str = Field(description="Canonical MAOI agent matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed serotonergic medication name")
    partner_agent: str = Field(
        description="Canonical serotonergic agent matched in the partner medication"
    )
    partner_drug_class: str = Field(
        description="Serotonergic drug class of the partner (e.g. SSRI, SNRI, triptan)"
    )
    severity: Severity
    rationale: str


class AntibioticDurationRisk(BaseModel, frozen=True):
    """An antibiotic course exceeding recommended duration or missing a stop date.

    Complements :class:`AntibioticStewardshipRisk` (fluoroquinolone indication,
    duplicate coverage, prolonged-course text cues) by evaluating explicit
    ``days_on_therapy`` against recommended duration cadences.
    """

    medication: str
    agent: str = Field(description="Canonical antibiotic agent matched in the medication name")
    finding_kind: str = Field(
        description=(
            "Finding kind: 'exceeds_recommended_duration' when days_on_therapy "
            "exceeds the recommended maximum, or 'missing_stop_date' when no "
            "stop date is documented"
        )
    )
    severity: Severity
    days_on_therapy: int = Field(
        ge=0, description="Days the patient has been on antibiotic therapy"
    )
    recommended_max_days: float = Field(
        ge=1, description="Recommended maximum duration in days for the agent/indication"
    )
    stop_date_provided: bool = Field(
        description="Whether a stop date / end-of-course date is documented"
    )
    indication_type: str | None = Field(
        default=None,
        description="Indication category used to select recommended duration (e.g. uti, pneumonia)",
    )
    rationale: str

    @field_validator("finding_kind")
    @classmethod
    def finding_kind_must_be_valid(cls, v: str) -> str:
        """Ensure finding_kind is exceeds_recommended_duration or missing_stop_date."""
        if v not in {"exceeds_recommended_duration", "missing_stop_date"}:
            raise ValueError(
                "finding_kind must be 'exceeds_recommended_duration' or 'missing_stop_date'"
            )
        return v


class ElectrolyteQtRisk(BaseModel, frozen=True):
    """A QT-prolonging medication with missing or low potassium/magnesium.

    Complements :class:`QtProlongationRisk` (additive QT drug count) and
    :class:`QtcMonitoringRisk` (ECG surveillance cadence) by evaluating
    electrolyte laboratory values against QT-prolonging agents.
    """

    medication: str = Field(
        description="Medication name containing the matched QT-prolonging agent"
    )
    agent: str = Field(description="Canonical QT-prolonging agent matched in the medication name")
    finding_kind: str = Field(
        description=(
            "Finding kind: 'missing_electrolytes' when potassium and/or magnesium "
            "is absent, 'low_potassium' when K < 3.5 mmol/L, or 'low_magnesium' "
            "when Mg < 1.7 mg/dL"
        )
    )
    severity: Severity
    potassium_mmol_l: float | None = Field(
        default=None,
        description="Serum potassium in mmol/L when known",
    )
    magnesium_mg_dl: float | None = Field(
        default=None,
        description="Serum magnesium in mg/dL when known",
    )
    rationale: str

    @field_validator("finding_kind")
    @classmethod
    def finding_kind_must_be_valid(cls, v: str) -> str:
        """Ensure finding_kind is a supported electrolyte-QT finding type."""
        if v not in {"missing_electrolytes", "low_potassium", "low_magnesium"}:
            raise ValueError(
                "finding_kind must be 'missing_electrolytes', 'low_potassium', or 'low_magnesium'"
            )
        return v


class OpioidBenzoRisk(BaseModel, frozen=True):
    """An opioid co-prescribed with a benzodiazepine or Z-drug hypnotic.

    Opioid plus benzodiazepine/Z-drug combinations increase the risk of profound
    CNS and respiratory depression. Distinct from :class:`OpioidMedRisk` (MED
    summation) and taper-schedule advisory flagging.
    """

    medication: str = Field(description="Medication name containing the matched opioid")
    agent: str = Field(description="Canonical opioid agent matched in the medication name")
    partner_medication: str = Field(
        description="Co-prescribed benzodiazepine or Z-drug medication name"
    )
    partner_agent: str = Field(
        description="Canonical benzodiazepine/Z-drug agent matched in the partner medication"
    )
    partner_drug_class: str = Field(
        description="Drug class of the partner (benzodiazepine or Z-drug)"
    )
    severity: Severity
    rationale: str


class ClinicalReasoning(BaseModel, frozen=True):
    """Structured output of a completed agent reasoning run.

    This is the canonical response type returned by the /analyze endpoint
    and persisted to the audit log.
    """

    session_id: str
    query: str
    state_reached: AgentState

    # Core reasoning outputs
    ranked_hypotheses: list[Hypothesis] = Field(default_factory=list)
    drug_interactions_flagged: list[DrugInteractionWarning] = Field(default_factory=list)

    # Confidence and uncertainty
    overall_confidence: float = Field(ge=0.0, le=1.0)
    uncertainty_flags: list[str] = Field(default_factory=list)
    escalated: bool = Field(
        default=False,
        description="True if agent reached ESCALATE state — human review required",
    )

    # Evidence provenance
    evidence_chain: list[RetrievedDocument] = Field(default_factory=list)
    entities_extracted: list[ClinicalEntity] = Field(default_factory=list)

    # Actionable output
    recommended_next_steps: list[str] = Field(default_factory=list)

    # Mandatory disclaimer — always populated
    disclaimer: str = Field(
        default=(
            "⚠️  RESEARCH USE ONLY. This output is generated by an AI system and has NOT "
            "been reviewed by a licensed clinician. It is NOT FDA-cleared and MUST NOT be "
            "used to guide clinical treatment decisions. Always consult a qualified "
            "healthcare professional."
        )
    )

    # Audit metadata
    model_used: str | None = None
    wall_time_seconds: float | None = None
    completed_at: datetime = Field(default_factory=datetime.utcnow)
    inputs_hash: str | None = None


class ChemoEmesisRisk(BaseModel, frozen=True):
    """Emetogenic chemotherapy with missing or inadequate antiemetic prophylaxis.

    Distinct from lactation chemotherapy flagging and QT-prolonging antiemetic
    surveillance; focuses on acute and delayed CINV prophylaxis gaps.
    """

    medication: str = Field(
        description="Medication name containing the matched emetogenic chemotherapy agent"
    )
    agent: str = Field(
        description="Canonical emetogenic chemotherapy agent matched in the medication name"
    )
    finding_kind: str = Field(
        description=(
            "Finding kind: 'missing_antiemetic_prophylaxis' when no antiemetic "
            "agents are documented, or 'delayed_phase_uncovered' when days_since_chemo "
            "falls in the delayed CINV window without delayed-phase coverage"
        )
    )
    severity: Severity
    emetogenic_level: str = Field(description="Emetogenicity level: 'high' or 'moderate'")
    days_since_chemo: int | None = Field(
        default=None,
        ge=0,
        description="Whole days since the most recent chemotherapy cycle when known",
    )
    antiemetic_agents_found: list[str] = Field(
        default_factory=list,
        description="Canonical antiemetic agents matched across the medication list",
    )
    rationale: str

    @field_validator("finding_kind")
    @classmethod
    def finding_kind_must_be_valid(cls, v: str) -> str:
        """Ensure finding_kind is a supported chemo-emesis finding type."""
        if v not in {"missing_antiemetic_prophylaxis", "delayed_phase_uncovered"}:
            raise ValueError(
                "finding_kind must be 'missing_antiemetic_prophylaxis' or 'delayed_phase_uncovered'"
            )
        return v

    @field_validator("emetogenic_level")
    @classmethod
    def emetogenic_level_must_be_valid(cls, v: str) -> str:
        """Ensure emetogenic_level is high or moderate."""
        if v not in {"high", "moderate"}:
            raise ValueError("emetogenic_level must be 'high' or 'moderate'")
        return v


class DigoxinToxicityRisk(BaseModel, frozen=True):
    """Digoxin with electrolyte or loop-diuretic factors elevating toxicity risk.

    Distinct from QT electrolyte checking; focuses on digoxin-specific narrow
    therapeutic index hazards from hypokalemia, hypomagnesemia, and loop diuretics.
    """

    medication: str = Field(description="Medication name containing the matched digoxin agent")
    agent: str = Field(description="Canonical digoxin agent matched in the medication name")
    finding_kind: str = Field(
        description=(
            "Finding kind: 'low_potassium', 'low_magnesium', or 'loop_diuretic_without_repletion'"
        )
    )
    severity: Severity
    potassium_mmol_l: float | None = Field(
        default=None,
        description="Serum potassium in mmol/L when supplied",
    )
    magnesium_mg_dl: float | None = Field(
        default=None,
        description="Serum magnesium in mg/dL when supplied",
    )
    loop_diuretic_agents_found: list[str] = Field(
        default_factory=list,
        description="Canonical loop diuretic agents matched across the medication list",
    )
    repletion_agents_found: list[str] = Field(
        default_factory=list,
        description="Canonical K/Mg repletion agents matched across the medication list",
    )
    rationale: str

    @field_validator("finding_kind")
    @classmethod
    def finding_kind_must_be_valid(cls, v: str) -> str:
        """Ensure finding_kind is a supported digoxin-toxicity finding type."""
        if v not in {"low_potassium", "low_magnesium", "loop_diuretic_without_repletion"}:
            raise ValueError(
                "finding_kind must be 'low_potassium', 'low_magnesium', or "
                "'loop_diuretic_without_repletion'"
            )
        return v


class StatinCyp3a4Risk(BaseModel, frozen=True):
    """A statin co-prescribed with a strong CYP3A4 inhibitor.

    Simvastatin, lovastatin, and atorvastatin with strong CYP3A4 inhibitors
    increase myopathy and rhabdomyolysis risk. Distinct from generic DDI and
    drug-food grapefruit screening.
    """

    medication: str = Field(description="Medication name containing the matched statin")
    agent: str = Field(description="Canonical statin agent matched in the medication name")
    partner_medication: str = Field(
        description="Co-prescribed strong CYP3A4 inhibitor medication name"
    )
    partner_agent: str = Field(
        description="Canonical CYP3A4 inhibitor agent matched in the partner medication"
    )
    severity: Severity
    rationale: str


class InsulinStackingRisk(BaseModel, frozen=True):
    """Overlapping rapid-acting insulin boluses or concurrent premix plus bolus regimens.

    Insulin stacking increases hypoglycemia risk from cumulative rapid-acting effect.
    """

    medication: str = Field(
        description="Medication name containing the matched insulin agent for this finding"
    )
    agent: str = Field(description="Canonical insulin agent matched in the medication name")
    finding_kind: str = Field(
        description=(
            "Finding kind: 'rapid_bolus_stacking' when bolus interval is too short "
            "without context, or 'premix_plus_bolus' for concurrent premix and bolus"
        )
    )
    partner_medication: str | None = Field(
        default=None,
        description="Partner bolus insulin medication name for premix_plus_bolus findings",
    )
    partner_agent: str | None = Field(
        default=None,
        description="Partner bolus insulin agent for premix_plus_bolus findings",
    )
    hours_since_last_bolus: float | None = Field(
        default=None,
        ge=0.0,
        description="Hours since the most recent rapid-acting bolus when supplied",
    )
    meal_context: bool = Field(
        default=False,
        description="True when a meal bolus context is documented",
    )
    correction_context: bool = Field(
        default=False,
        description="True when a correction bolus context is documented",
    )
    severity: Severity
    rationale: str

    @field_validator("finding_kind")
    @classmethod
    def finding_kind_must_be_valid(cls, v: str) -> str:
        """Ensure finding_kind is a supported insulin-stacking finding type."""
        if v not in {"rapid_bolus_stacking", "premix_plus_bolus"}:
            raise ValueError("finding_kind must be 'rapid_bolus_stacking' or 'premix_plus_bolus'")
        return v


class TripleWhammyRisk(BaseModel, frozen=True):
    """NSAID + ACEI/ARB/ARNI + loop/thiazide diuretic concurrent therapy.

    The "triple whammy" combination impairs renal autoregulation and increases
    acute kidney injury risk. Distinct from generic DDI screening.
    """

    nsaid_medication: str = Field(description="Medication name containing the matched NSAID")
    nsaid_agent: str = Field(description="Canonical NSAID agent matched in the medication name")
    acei_arb_medication: str = Field(
        description="Medication name containing the matched ACEI, ARB, or ARNI agent"
    )
    acei_arb_agent: str = Field(
        description="Canonical ACEI/ARB/ARNI agent matched in the medication name"
    )
    diuretic_medication: str = Field(
        description="Medication name containing the matched loop or thiazide diuretic"
    )
    diuretic_agent: str = Field(
        description="Canonical loop/thiazide diuretic agent matched in the medication name"
    )
    severity: Severity
    rationale: str


class MtxFolateRisk(BaseModel, frozen=True):
    """Methotrexate prescribed without folic acid / folate / leucovorin co-therapy.

    Missing folate co-therapy increases mucositis and hematologic toxicity risk.
    Distinct from generic DDI screening.
    """

    medication: str = Field(description="Medication name containing the matched methotrexate agent")
    agent: str = Field(description="Canonical methotrexate agent matched in the medication name")
    severity: Severity
    rationale: str


class DigoxinAmioRisk(BaseModel, frozen=True):
    """Digoxin co-prescribed with amiodarone requiring serum digoxin monitoring.

    Amiodarone inhibits digoxin clearance and can approximately double digoxin
    levels. Distinct from digoxin toxicity electrolyte screening and generic DDI.
    """

    medication: str = Field(description="Medication name containing the matched digoxin agent")
    agent: str = Field(description="Canonical digoxin agent matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed amiodarone medication name")
    partner_agent: str = Field(
        description="Canonical amiodarone agent matched in the partner medication"
    )
    severity: Severity
    rationale: str


class WarfarinNsaidRisk(BaseModel, frozen=True):
    """Warfarin-class anticoagulant co-prescribed with an NSAID bleed intensifier.

    Concurrent warfarin anticoagulation with an NSAID increases major bleeding
    risk via GI mucosal injury and platelet dysfunction. Distinct from the
    broader anticoagulation bleeding-risk panel and generic DDI screening.
    """

    medication: str = Field(
        description="Medication name containing the matched warfarin-class agent"
    )
    agent: str = Field(description="Canonical warfarin-class agent matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed NSAID medication name")
    partner_agent: str = Field(
        description="Canonical NSAID agent matched in the partner medication"
    )
    severity: Severity
    rationale: str


class AceiArbDuplicationRisk(BaseModel, frozen=True):
    """Dual RAAS blockade from concurrent ACEI, ARB, and/or ARNI therapy.

    Combining ≥2 distinct renin–angiotensin classes increases hyperkalemia,
    hypotension, and renal risk without outcome benefit. Distinct from
    triple-whammy renal risk and generic DDI screening.
    """

    medication_a: str = Field(description="Medication name for the first RAAS-class agent")
    agent_a: str = Field(description="Canonical agent matched in medication_a")
    class_a: str = Field(description="RAAS class of agent_a: ACEI, ARB, or ARNI")
    medication_b: str = Field(description="Medication name for the second RAAS-class agent")
    agent_b: str = Field(description="Canonical agent matched in medication_b")
    class_b: str = Field(description="RAAS class of agent_b: ACEI, ARB, or ARNI")
    classes_present: list[str] = Field(
        description="Distinct RAAS classes present on the medication list (ACEI/ARB/ARNI)"
    )
    severity: Severity
    rationale: str


class TramadolSsriRisk(BaseModel, frozen=True):
    """Tramadol co-prescribed with an SSRI/SNRI elevating seizure and serotonin risk.

    Tramadol lowers seizure threshold and is serotonergic; stacking with
    SSRI/SNRI agents compounds both hazards. Distinct from MAOI serotonin
    cross-checks and broad serotonin-syndrome screening.
    """

    medication: str = Field(description="Medication name containing the matched tramadol agent")
    agent: str = Field(description="Canonical tramadol agent matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed SSRI/SNRI medication name")
    partner_agent: str = Field(
        description="Canonical SSRI/SNRI agent matched in the partner medication"
    )
    partner_drug_class: str = Field(description="Partner drug class: SSRI or SNRI")
    severity: Severity
    rationale: str


class ClozapineAncRisk(BaseModel, frozen=True):
    """Clozapine therapy requiring absolute neutrophil count (ANC) monitoring.

    Clozapine carries a boxed warning for severe neutropenia / agranulocytosis
    and requires scheduled ANC monitoring. Distinct from generic boxed-warning
    panels and generic DDI screening.
    """

    medication: str = Field(
        description="Medication name containing the matched clozapine-class agent"
    )
    agent: str = Field(description="Canonical clozapine-class agent matched in the medication name")
    severity: Severity
    rationale: str


class Sglt2LoopRisk(BaseModel, frozen=True):
    """SGLT2 inhibitor co-prescribed with a loop diuretic (volume depletion risk).

    Concurrent SGLT2 inhibitor and loop diuretic therapy increases volume
    depletion, hypotension, and acute kidney injury risk. Distinct from
    triple-whammy renal risk and generic DDI screening.
    """

    medication: str = Field(description="Medication name containing the matched SGLT2 inhibitor")
    agent: str = Field(description="Canonical SGLT2 inhibitor matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed loop diuretic medication name")
    partner_agent: str = Field(
        description="Canonical loop diuretic agent matched in the partner medication"
    )
    severity: Severity
    rationale: str


class MacrolideDigoxinRisk(BaseModel, frozen=True):
    """Digoxin co-prescribed with a P-gp-inhibiting macrolide (toxicity risk).

    Clarithromycin and erythromycin inhibit P-glycoprotein and can raise digoxin
    serum concentrations, increasing digoxin toxicity risk. Azithromycin is
    excluded as a weaker P-gp inhibitor. Distinct from digoxin+amiodarone
    monitoring and digoxin toxicity electrolyte screening.
    """

    medication: str = Field(description="Medication name containing the matched digoxin agent")
    agent: str = Field(description="Canonical digoxin agent matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed macrolide medication name")
    partner_agent: str = Field(
        description="Canonical P-gp-inhibiting macrolide matched in the partner medication"
    )
    severity: Severity
    rationale: str


class LithiumNsaidRisk(BaseModel, frozen=True):
    """Lithium-class agent co-prescribed with an NSAID (toxicity risk).

    NSAIDs can reduce renal lithium clearance and raise serum lithium
    concentrations, increasing lithium toxicity risk. Acetaminophen and
    paracetamol are excluded because they are not NSAIDs. Distinct from
    lactation, pregnancy, renal-dose, and generic DDI screening.
    """

    medication: str = Field(
        description="Medication name containing the matched lithium-class agent"
    )
    agent: str = Field(description="Canonical lithium-class agent matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed NSAID medication name")
    partner_agent: str = Field(
        description="Canonical NSAID agent matched in the partner medication"
    )
    severity: Severity
    rationale: str


class DoacAntiplateletRisk(BaseModel, frozen=True):
    """DOAC co-prescribed with an antiplatelet bleed intensifier.

    Concurrent DOAC anticoagulation with antiplatelet therapy intensifies major
    bleeding risk. Distinct from the broader anticoagulation bleeding-risk panel,
    warfarin + NSAID intensifier screening, and generic DDI flagging.
    """

    medication: str = Field(description="Medication name containing the matched DOAC agent")
    agent: str = Field(description="Canonical DOAC agent matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed antiplatelet medication name")
    partner_agent: str = Field(
        description="Canonical antiplatelet agent matched in the partner medication"
    )
    severity: Severity
    rationale: str


class MtxTmpsmxRisk(BaseModel, frozen=True):
    """Methotrexate co-prescribed with TMP-SMX (myelosuppression / toxicity risk).

    Trimethoprim–sulfamethoxazole can potentiate methotrexate antifolate toxicity
    and increase myelosuppression risk. Distinct from methotrexate-without-folate
    co-therapy screening and generic DDI flagging.
    """

    medication: str = Field(description="Medication name containing the matched methotrexate agent")
    agent: str = Field(description="Canonical methotrexate agent matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed TMP-SMX medication name")
    partner_agent: str = Field(
        description="Canonical TMP-SMX panel agent matched in the partner medication"
    )
    severity: Severity
    rationale: str


class AmioWarfarinRisk(BaseModel, frozen=True):
    """Amiodarone co-prescribed with warfarin (INR potentiation / bleeding risk).

    Amiodarone inhibits warfarin metabolism and can raise INR, increasing bleeding
    risk. Distinct from digoxin + amiodarone level monitoring, warfarin + NSAID
    intensifier screening, and generic DDI flagging.
    """

    medication: str = Field(
        description="Medication name containing the matched amiodarone-class agent"
    )
    agent: str = Field(
        description="Canonical amiodarone-class agent matched in the medication name"
    )
    partner_medication: str = Field(description="Co-prescribed warfarin-class medication name")
    partner_agent: str = Field(
        description="Canonical warfarin-class agent matched in the partner medication"
    )
    severity: Severity
    rationale: str


class FluoroquinoloneWarfarinRisk(BaseModel, frozen=True):
    """Fluoroquinolone co-prescribed with warfarin (INR / bleeding risk).

    Fluoroquinolone antibiotics can potentiate warfarin anticoagulation,
    increasing INR variability and bleeding risk. Distinct from amiodarone +
    warfarin, warfarin + NSAID, and generic DDI screening.
    """

    medication: str = Field(
        description="Medication name containing the matched fluoroquinolone agent"
    )
    agent: str = Field(description="Canonical fluoroquinolone matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed warfarin-class medication name")
    partner_agent: str = Field(
        description="Canonical warfarin-class agent matched in the partner medication"
    )
    severity: Severity
    rationale: str


class AceiKsparingRisk(BaseModel, frozen=True):
    """ACE inhibitor/ARB co-prescribed with a potassium-sparing agent.

    Combining ACEI/ARB therapy with a potassium-sparing diuretic or
    mineralocorticoid receptor antagonist increases hyperkalemia and renal risk.
    Distinct from ACEI + ARB dual-blockade duplication screening.
    """

    medication: str = Field(description="Medication name containing the matched ACEI/ARB agent")
    agent: str = Field(description="Canonical ACEI/ARB agent matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed potassium-sparing medication name")
    partner_agent: str = Field(
        description="Canonical potassium-sparing agent matched in the partner medication"
    )
    severity: Severity
    rationale: str


class NsaidSsriBleedRisk(BaseModel, frozen=True):
    """NSAID co-prescribed with an SSRI/SNRI bleeding intensifier.

    NSAID-related GI mucosal injury and platelet inhibition combined with
    SSRI/SNRI-related impairment of platelet aggregation increases bleeding
    risk. Distinct from warfarin + NSAID and tramadol + SSRI/SNRI screening.
    """

    medication: str = Field(description="Medication name containing the matched NSAID agent")
    agent: str = Field(description="Canonical NSAID matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed SSRI/SNRI medication name")
    partner_agent: str = Field(
        description="Canonical SSRI/SNRI agent matched in the partner medication"
    )
    partner_drug_class: str = Field(description="Partner drug class: SSRI or SNRI")
    severity: Severity
    rationale: str


class FluoroquinoloneNsaidRisk(BaseModel, frozen=True):
    """Fluoroquinolone co-prescribed with an NSAID (CNS / seizure risk).

    Fluoroquinolones can lower the seizure threshold and cause CNS stimulation;
    concurrent NSAID use intensifies that CNS risk. Distinct from fluoroquinolone
    + warfarin INR potentiation and warfarin + NSAID bleeding intensification.
    """

    medication: str = Field(
        description="Medication name containing the matched fluoroquinolone agent"
    )
    agent: str = Field(description="Canonical fluoroquinolone matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed NSAID medication name")
    partner_agent: str = Field(
        description="Canonical NSAID agent matched in the partner medication"
    )
    severity: Severity
    rationale: str


class AceiTrimethoprimRisk(BaseModel, frozen=True):
    """ACE inhibitor/ARB co-prescribed with trimethoprim / TMP-SMX.

    Combining ACEI/ARB therapy with trimethoprim (including TMP-SMX) increases
    hyperkalemia risk via additive potassium-sparing effects. Distinct from
    ACEI/ARB + potassium-sparing diuretic screening and methotrexate + TMP-SMX
    myelosuppression screening.
    """

    medication: str = Field(description="Medication name containing the matched ACEI/ARB agent")
    agent: str = Field(description="Canonical ACEI/ARB agent matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed trimethoprim / TMP-SMX medication")
    partner_agent: str = Field(
        description="Canonical trimethoprim / TMP-SMX agent matched in the partner medication"
    )
    severity: Severity
    rationale: str


class SsriTriptanRisk(BaseModel, frozen=True):
    """SSRI/SNRI co-prescribed with a triptan (serotonin-syndrome pair risk).

    Combining an SSRI or SNRI with a triptan antimigraine agent increases
    serotonin-syndrome risk. Distinct from the broader multi-class serotonin
    syndrome panel and NSAID + SSRI/SNRI bleeding intensification.
    """

    medication: str = Field(description="Medication name containing the matched SSRI/SNRI agent")
    agent: str = Field(description="Canonical SSRI/SNRI agent matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed triptan medication name")
    partner_agent: str = Field(
        description="Canonical triptan agent matched in the partner medication"
    )
    antidepressant_class: str = Field(description="Antidepressant drug class: SSRI or SNRI")
    severity: Severity
    rationale: str


class FluoroquinoloneCorticosteroidRisk(BaseModel, frozen=True):
    """Fluoroquinolone co-prescribed with a corticosteroid (tendon rupture risk).

    Concurrent fluoroquinolone and systemic corticosteroid therapy increases
    tendon rupture and tendinopathy risk. Distinct from fluoroquinolone + NSAID
    CNS/seizure risk and fluoroquinolone + warfarin INR potentiation.
    """

    medication: str = Field(
        description="Medication name containing the matched fluoroquinolone agent"
    )
    agent: str = Field(description="Canonical fluoroquinolone agent matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed corticosteroid medication name")
    partner_agent: str = Field(
        description="Canonical corticosteroid agent matched in the partner medication"
    )
    severity: Severity
    rationale: str


class DigoxinVerapamilRisk(BaseModel, frozen=True):
    """Digoxin co-prescribed with verapamil (toxicity via P-gp / reduced clearance).

    Verapamil inhibits P-glycoprotein and reduces digoxin clearance, raising
    digoxin serum concentrations. Distinct from digoxin + amiodarone level
    monitoring and macrolide + digoxin P-gp interaction screening.
    """

    medication: str = Field(description="Medication name containing the matched digoxin agent")
    agent: str = Field(description="Canonical digoxin agent matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed verapamil medication name")
    partner_agent: str = Field(
        description="Canonical verapamil agent matched in the partner medication"
    )
    severity: Severity
    rationale: str


class StatinMacrolideRisk(BaseModel, frozen=True):
    """Statin co-prescribed with a strong CYP3A4-inhibiting macrolide.

    Clarithromycin and erythromycin increase systemic exposure to
    CYP3A4-metabolized statins, raising myopathy and rhabdomyolysis risk.
    Distinct from the broader statin + strong CYP3A4 inhibitor panel.
    """

    medication: str = Field(description="Medication name containing the matched statin agent")
    agent: str = Field(description="Canonical statin agent matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed macrolide medication name")
    partner_agent: str = Field(
        description="Canonical macrolide agent matched in the partner medication"
    )
    severity: Severity
    rationale: str


class WarfarinAzoleRisk(BaseModel, frozen=True):
    """Warfarin co-prescribed with a systemic azole antifungal.

    Systemic azoles can inhibit CYP2C9 and other warfarin-metabolizing CYP
    pathways, elevating INR and bleeding risk. Topical clotrimazole is outside
    this focused interaction panel.
    """

    medication: str = Field(description="Medication name containing the matched warfarin agent")
    agent: str = Field(description="Canonical warfarin agent matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed systemic azole medication name")
    partner_agent: str = Field(
        description="Canonical systemic azole agent matched in the partner medication"
    )
    severity: Severity
    rationale: str


class MtxNsaidRisk(BaseModel, frozen=True):
    """Methotrexate co-prescribed with an NSAID (reduced-clearance toxicity).

    NSAIDs can reduce renal methotrexate elimination and increase exposure,
    raising myelosuppression, mucositis, renal injury, and hepatotoxicity risk.
    Distinct from methotrexate + TMP-SMX and other NSAID interaction controls.
    """

    medication: str = Field(description="Medication name containing methotrexate")
    agent: str = Field(description="Canonical methotrexate agent matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed NSAID medication name")
    partner_agent: str = Field(
        description="Canonical NSAID agent matched in the partner medication"
    )
    severity: Severity
    rationale: str


class AceiSacubitrilRisk(BaseModel, frozen=True):
    """ACE inhibitor overlapping with sacubitril-containing therapy.

    Concurrent ACE and neprilysin inhibition substantially increases
    angioedema risk. A 36-hour washout is required between an ACE inhibitor and
    sacubitril-containing therapy.
    """

    medication: str = Field(description="Medication name containing the matched ACE inhibitor")
    agent: str = Field(description="Canonical ACE inhibitor matched in the medication name")
    partner_medication: str = Field(
        description="Co-prescribed sacubitril-containing medication name"
    )
    partner_agent: str = Field(
        description="Canonical sacubitril or Entresto agent matched in the partner medication"
    )
    severity: Severity
    rationale: str


class DoacNsaidRisk(BaseModel, frozen=True):
    """DOAC co-prescribed with an NSAID (bleeding intensifier).

    NSAIDs combined with direct oral anticoagulants increase major bleeding risk
    through anticoagulation plus GI mucosal injury and platelet dysfunction.
    Distinct from DOAC + antiplatelet and warfarin + NSAID controls.
    """

    medication: str = Field(description="Medication name containing the matched DOAC agent")
    agent: str = Field(description="Canonical DOAC agent matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed NSAID medication name")
    partner_agent: str = Field(
        description="Canonical NSAID agent matched in the partner medication"
    )
    severity: Severity
    rationale: str


class Sglt2RaasiRisk(BaseModel, frozen=True):
    """SGLT2 inhibitor co-prescribed with ACEI/ARB/ARNI RAAS therapy.

    Concurrent SGLT2 inhibitor and RAAS blockade increases volume depletion,
    hypotension, acute kidney injury, and hyperkalemia risk. Distinct from
    SGLT2 + loop diuretic and focused ACEI duplication controls.
    """

    medication: str = Field(description="Medication name containing the matched SGLT2 agent")
    agent: str = Field(description="Canonical SGLT2 agent matched in the medication name")
    partner_medication: str = Field(description="Co-prescribed ACEI/ARB/ARNI medication name")
    partner_agent: str = Field(description="Canonical RAAS agent matched in the partner medication")
    severity: Severity
    rationale: str


class ClopidogrelPpiRisk(BaseModel, frozen=True):
    """Clopidogrel co-prescribed with a CYP2C19-inhibiting PPI.

    Omeprazole and esomeprazole inhibit CYP2C19, reducing conversion of
    clopidogrel to its active metabolite and potentially diminishing antiplatelet
    effect. Distinct from DOAC + antiplatelet screening.
    """

    medication: str = Field(description="Medication name containing the matched clopidogrel agent")
    agent: str = Field(description="Canonical clopidogrel agent matched in the medication name")
    partner_medication: str = Field(
        description="Co-prescribed CYP2C19-inhibiting PPI medication name"
    )
    partner_agent: str = Field(description="Canonical PPI agent matched in the partner medication")
    severity: Severity
    rationale: str


class LinezolidSsriRisk(BaseModel, frozen=True):
    """Linezolid co-prescribed with an SSRI or SNRI.

    Linezolid's reversible MAOI-like activity can combine with serotonergic
    antidepressants to precipitate serotonin syndrome.
    """

    medication: str = Field(description="Medication name containing linezolid")
    agent: str = Field(description="Canonical linezolid agent")
    partner_medication: str = Field(description="Co-prescribed SSRI/SNRI medication name")
    partner_agent: str = Field(description="Canonical SSRI/SNRI agent")
    severity: Severity
    rationale: str


class PpiMtxRisk(BaseModel, frozen=True):
    """Methotrexate co-prescribed with a proton-pump inhibitor.

    PPIs may reduce methotrexate clearance and increase exposure and toxicity
    risk. Distinct from methotrexate + NSAID and clopidogrel + PPI controls.
    """

    medication: str = Field(description="Medication name containing methotrexate")
    agent: str = Field(description="Canonical methotrexate agent")
    partner_medication: str = Field(description="Co-prescribed PPI medication name")
    partner_agent: str = Field(description="Canonical PPI agent")
    severity: Severity
    rationale: str


class LithiumAceiRisk(BaseModel, frozen=True):
    """Lithium co-prescribed with an ACE inhibitor or ARB.

    ACE inhibitors and ARBs may reduce renal lithium clearance and increase
    serum lithium concentrations and toxicity risk.
    """

    medication: str = Field(description="Medication name containing a lithium agent")
    agent: str = Field(description="Canonical lithium agent")
    partner_medication: str = Field(description="Co-prescribed ACEI/ARB medication name")
    partner_agent: str = Field(description="Canonical ACEI/ARB agent")
    severity: Severity
    rationale: str


class TheophyllineCiproRisk(BaseModel, frozen=True):
    """Theophylline co-prescribed with a strong CYP1A2-inhibiting quinolone.

    Ciprofloxacin and enoxacin can reduce theophylline clearance, raise serum
    concentrations, and increase the risk of seizures and serious arrhythmias.
    """

    medication: str = Field(description="Medication name containing a theophylline agent")
    agent: str = Field(description="Canonical theophylline agent")
    partner_medication: str = Field(description="Co-prescribed quinolone medication name")
    partner_agent: str = Field(description="Canonical CYP1A2-inhibiting quinolone agent")
    severity: Severity
    rationale: str


class AmiodaroneDigoxinRisk(BaseModel, frozen=True):
    """Amiodarone co-prescribed with digoxin.

    Amiodarone inhibits P-glycoprotein and reduces digoxin clearance, which can
    substantially increase serum digoxin concentrations and toxicity risk.
    """

    medication: str = Field(description="Medication name containing an amiodarone agent")
    agent: str = Field(description="Canonical amiodarone agent")
    partner_medication: str = Field(description="Co-prescribed digoxin medication name")
    partner_agent: str = Field(description="Canonical digoxin agent")
    severity: Severity
    rationale: str


class CarbamazepineMacrolideRisk(BaseModel, frozen=True):
    """Carbamazepine co-prescribed with a CYP3A4-inhibiting macrolide.

    Clarithromycin and erythromycin can reduce carbamazepine metabolism, raise
    serum concentrations, and increase dose-related toxicity risk.
    """

    medication: str = Field(description="Medication name containing a carbamazepine agent")
    agent: str = Field(description="Canonical carbamazepine agent")
    partner_medication: str = Field(description="Co-prescribed macrolide medication name")
    partner_agent: str = Field(description="Canonical CYP3A4-inhibiting macrolide agent")
    severity: Severity
    rationale: str


class WarfarinMetronidazoleRisk(BaseModel, frozen=True):
    """Warfarin co-prescribed with metronidazole or tinidazole.

    Nitroimidazole-related CYP2C9 inhibition can reduce warfarin clearance,
    elevate INR, and increase bleeding risk.
    """

    medication: str = Field(description="Medication name containing a warfarin agent")
    agent: str = Field(description="Canonical warfarin agent")
    partner_medication: str = Field(
        description="Co-prescribed nitroimidazole antibiotic medication name"
    )
    partner_agent: str = Field(description="Canonical nitroimidazole antibiotic agent")
    severity: Severity
    rationale: str


class ColchicineCyp3a4Risk(BaseModel, frozen=True):
    """Colchicine co-prescribed with a strong CYP3A4/P-gp inhibitor.

    Strong CYP3A4 and/or P-glycoprotein inhibition can markedly increase
    colchicine exposure and cause severe or fatal toxicity (FDA
    boxed-warning territory). Distinct from the fentanyl CYP3A4 checker.
    """

    medication: str = Field(description="Medication name containing a colchicine agent")
    agent: str = Field(description="Canonical colchicine agent")
    partner_medication: str = Field(
        description="Co-prescribed strong CYP3A4/P-gp inhibitor medication name"
    )
    partner_agent: str = Field(description="Canonical strong CYP3A4/P-gp inhibitor agent")
    severity: Severity
    rationale: str


class LithiumThiazideRisk(BaseModel, frozen=True):
    """Lithium co-prescribed with a thiazide or thiazide-like diuretic.

    Thiazides can reduce renal lithium clearance, raise serum lithium
    concentrations, and cause toxicity.
    """

    medication: str = Field(description="Medication name containing a lithium agent")
    agent: str = Field(description="Canonical lithium agent")
    partner_medication: str = Field(description="Co-prescribed thiazide diuretic medication name")
    partner_agent: str = Field(description="Canonical thiazide diuretic agent")
    severity: Severity
    rationale: str


class TramadolBupropionRisk(BaseModel, frozen=True):
    """Tramadol co-prescribed with bupropion, compounding seizure risk.

    Both tramadol and bupropion lower the seizure threshold. This focused
    record is distinct from tramadol + SSRI/SNRI screening.
    """

    medication: str = Field(description="Medication name containing a tramadol agent")
    agent: str = Field(description="Canonical tramadol agent")
    partner_medication: str = Field(description="Co-prescribed bupropion medication name")
    partner_agent: str = Field(description="Canonical bupropion agent")
    severity: Severity
    rationale: str


class MtxPenicillinRisk(BaseModel, frozen=True):
    """Methotrexate co-prescribed with a penicillin-class antibiotic.

    Penicillin-class antibiotics can reduce renal methotrexate clearance
    and increase toxicity risk. This record is distinct from methotrexate
    + NSAID and methotrexate + TMP-SMX controls.
    """

    medication: str = Field(description="Medication name containing a methotrexate agent")
    agent: str = Field(description="Canonical methotrexate agent")
    partner_medication: str = Field(description="Co-prescribed penicillin medication name")
    partner_agent: str = Field(description="Canonical penicillin agent")
    severity: Severity
    rationale: str


class SildenafilNitrateRisk(BaseModel, frozen=True):
    """Sildenafil co-prescribed with an organic nitrate.

    PDE-5 inhibition amplifies nitrate-mediated cyclic-GMP vasodilation
    and can cause profound, life-threatening hypotension.
    """

    medication: str = Field(description="Medication name containing a sildenafil agent")
    agent: str = Field(description="Canonical sildenafil agent")
    partner_medication: str = Field(description="Co-prescribed nitrate medication name")
    partner_agent: str = Field(description="Canonical nitrate agent")
    severity: Severity
    rationale: str


class AllopurinolAzathioprineRisk(BaseModel, frozen=True):
    """Allopurinol co-prescribed with azathioprine or mercaptopurine.

    Xanthine oxidase inhibition increases thiopurine exposure and can cause
    severe myelosuppression and other toxicity.
    """

    medication: str = Field(description="Medication name containing an allopurinol agent")
    agent: str = Field(description="Canonical allopurinol agent")
    partner_medication: str = Field(description="Co-prescribed thiopurine medication name")
    partner_agent: str = Field(description="Canonical azathioprine/mercaptopurine agent")
    severity: Severity
    rationale: str


class CodeineCyp2d6Risk(BaseModel, frozen=True):
    """Codeine co-prescribed with a strong CYP2D6 inhibitor.

    Codeine requires CYP2D6 conversion to morphine; strong inhibitors can
    reduce analgesia and alter exposure. Distinct from other opioid checkers.
    """

    medication: str = Field(description="Medication name containing a codeine agent")
    agent: str = Field(description="Canonical codeine agent")
    partner_medication: str = Field(description="Co-prescribed CYP2D6-inhibitor medication name")
    partner_agent: str = Field(description="Canonical strong CYP2D6 inhibitor")
    severity: Severity
    rationale: str


class AceiPotassiumRisk(BaseModel, frozen=True):
    """ACE inhibitor/ARB co-prescribed with a potassium supplement.

    Concurrent exogenous potassium increases hyperkalemia risk. Distinct from
    ACEI/ARB + potassium-sparing diuretic and ACEI/ARB + trimethoprim screening.
    """

    medication: str = Field(description="Medication name containing an ACEI or ARB agent")
    agent: str = Field(description="Canonical ACEI or ARB agent")
    partner_medication: str = Field(
        description="Co-prescribed potassium-supplement medication name"
    )
    partner_agent: str = Field(description="Canonical potassium-supplement agent")
    severity: Severity
    rationale: str


class IsotretinoinTetracyclineRisk(BaseModel, frozen=True):
    """Isotretinoin co-prescribed with a tetracycline-class antibiotic.

    Both agents are independently associated with idiopathic intracranial
    hypertension; co-prescription can precipitate pseudotumor cerebri with
    irreversible vision loss.
    """

    medication: str = Field(description="Medication name containing an isotretinoin agent")
    agent: str = Field(description="Canonical isotretinoin agent")
    partner_medication: str = Field(
        description="Co-prescribed tetracycline-class antibiotic medication name"
    )
    partner_agent: str = Field(description="Canonical tetracycline-class agent")
    severity: Severity
    rationale: str


class MetforminContrastRisk(BaseModel, frozen=True):
    """Metformin co-prescribed with iodinated contrast media.

    Iodinated contrast can transiently impair renal clearance of metformin,
    and accumulation can precipitate life-threatening lactic acidosis. Distinct
    from general metformin renal-dose checking.
    """

    medication: str = Field(description="Medication name containing a metformin agent")
    agent: str = Field(description="Canonical metformin agent")
    partner_medication: str = Field(
        description="Co-prescribed iodinated-contrast-media medication name"
    )
    partner_agent: str = Field(description="Canonical iodinated-contrast-media agent")
    severity: Severity
    rationale: str


class MethadoneQtRisk(BaseModel, frozen=True):
    """Methadone co-prescribed with another QT-prolonging medication.

    Methadone's baseline QT-prolonging effect can be intensified by a second
    QT-prolonging agent, increasing torsades de pointes risk. Distinct from the
    general multi-drug QT-prolongation screen.
    """

    medication: str = Field(description="Medication name containing a methadone agent")
    agent: str = Field(description="Canonical methadone agent")
    partner_medication: str = Field(description="Co-prescribed QT-prolonging medication name")
    partner_agent: str = Field(description="Canonical QT-prolonging partner agent")
    severity: Severity
    rationale: str


class ValproateCarbapenemRisk(BaseModel, frozen=True):
    """Valproate co-prescribed with a carbapenem antibiotic.

    Carbapenems can precipitously lower serum valproate levels, increasing
    breakthrough seizure risk. Distinct from general AED interaction screens.
    """

    medication: str = Field(description="Medication name containing a valproate agent")
    agent: str = Field(description="Canonical valproate agent")
    partner_medication: str = Field(description="Co-prescribed carbapenem medication name")
    partner_agent: str = Field(description="Canonical carbapenem partner agent")
    severity: Severity
    rationale: str


class LamotrigineValproateRisk(BaseModel, frozen=True):
    """Lamotrigine co-prescribed with a valproate agent.

    Valproate inhibits lamotrigine metabolism, raising SJS/TEN risk. Distinct
    from the valproate × carbapenem precipitous level-drop checker.
    """

    medication: str = Field(description="Medication name containing a lamotrigine agent")
    agent: str = Field(description="Canonical lamotrigine agent")
    partner_medication: str = Field(description="Co-prescribed valproate medication name")
    partner_agent: str = Field(description="Canonical valproate partner agent")
    severity: Severity
    rationale: str


class FentanylCyp3a4Risk(BaseModel, frozen=True):
    """Fentanyl co-prescribed with a CYP3A4 inhibitor.

    CYP3A4 inhibition raises fentanyl exposure and respiratory-depression risk.
    Distinct from opioid + benzodiazepine and general opioid MED checkers.
    """

    medication: str = Field(description="Medication name containing a fentanyl agent")
    agent: str = Field(description="Canonical fentanyl agent")
    partner_medication: str = Field(description="Co-prescribed CYP3A4-inhibitor medication name")
    partner_agent: str = Field(description="Canonical CYP3A4-inhibitor partner agent")
    severity: Severity
    rationale: str


class ClozapineCyp1a2Risk(BaseModel, frozen=True):
    """Clozapine co-prescribed with a strong CYP1A2 inhibitor.

    Strong CYP1A2 inhibition elevates clozapine levels and increases seizure
    and myocarditis risk. Distinct from the clozapine ANC monitoring checker.
    """

    medication: str = Field(description="Medication name containing a clozapine agent")
    agent: str = Field(description="Canonical clozapine agent")
    partner_medication: str = Field(
        description="Co-prescribed strong CYP1A2-inhibitor medication name"
    )
    partner_agent: str = Field(description="Canonical strong CYP1A2-inhibitor partner agent")
    severity: Severity
    rationale: str


class DoacInducerRisk(BaseModel, frozen=True):
    """DOAC co-prescribed with a strong CYP3A4/P-gp inducer.

    Strong induction can reduce DOAC exposure and increase thrombosis risk.
    Distinct from warfarin interaction checkers and DOAC bleeding controls.
    """

    medication: str = Field(description="Medication name containing a DOAC agent")
    agent: str = Field(description="Canonical DOAC agent")
    partner_medication: str = Field(description="Co-prescribed strong inducer medication name")
    partner_agent: str = Field(description="Canonical strong inducer partner agent")
    severity: Severity
    rationale: str


class WarfarinTmpsmxRisk(BaseModel, frozen=True):
    """Warfarin co-prescribed with TMP-SMX (INR elevation / bleed risk).

    TMP-SMX can potentiate warfarin anticoagulation and increase bleeding risk.
    Distinct from methotrexate + TMP-SMX and fluoroquinolone + warfarin checkers.
    """

    medication: str = Field(description="Medication name containing a warfarin agent")
    agent: str = Field(description="Canonical warfarin agent")
    partner_medication: str = Field(description="Co-prescribed TMP-SMX medication name")
    partner_agent: str = Field(description="Canonical TMP-SMX partner agent")
    severity: Severity
    rationale: str


class QuetiapineCyp3a4Risk(BaseModel, frozen=True):
    """Quetiapine co-prescribed with a strong CYP3A4 inhibitor.

    Strong CYP3A4 inhibition elevates quetiapine exposure and intensifies
    QT-prolongation and sedation risk. Distinct from colchicine and fentanyl
    CYP3A4 checkers.
    """

    medication: str = Field(description="Medication name containing a quetiapine agent")
    agent: str = Field(description="Canonical quetiapine agent")
    partner_medication: str = Field(
        description="Co-prescribed strong CYP3A4-inhibitor medication name"
    )
    partner_agent: str = Field(description="Canonical strong CYP3A4-inhibitor partner agent")
    severity: Severity
    rationale: str


class StatinFibrateRisk(BaseModel, frozen=True):
    """Statin co-prescribed with a fibrate (myopathy / rhabdomyolysis risk).

    Concurrent statin–fibrate therapy intensifies skeletal-muscle toxicity.
    Distinct from statin CYP3A4 and statin macrolide checkers.
    """

    medication: str = Field(description="Medication name containing a statin agent")
    agent: str = Field(description="Canonical statin agent")
    partner_medication: str = Field(description="Co-prescribed fibrate medication name")
    partner_agent: str = Field(description="Canonical fibrate partner agent")
    severity: Severity
    rationale: str


class MethotrexateNsaidRisk(BaseModel, frozen=True):
    """Methotrexate co-prescribed with an NSAID (reduced clearance / toxicity).

    NSAIDs can reduce renal methotrexate clearance and increase toxicity risk.
    Distinct from legacy `MtxNsaidRisk` and methotrexate + TMP-SMX checkers.
    """

    medication: str = Field(description="Medication name containing a methotrexate agent")
    agent: str = Field(description="Canonical methotrexate agent")
    partner_medication: str = Field(description="Co-prescribed NSAID medication name")
    partner_agent: str = Field(description="Canonical NSAID partner agent")
    severity: Severity
    rationale: str


class MethotrexateTrimethoprimRisk(BaseModel, frozen=True):
    """Methotrexate co-prescribed with trimethoprim / TMP-SMX (antifolate synergy).

    Trimethoprim intensifies antifolate toxicity and can precipitate pancytopenia.
    Distinct from legacy `MtxTmpsmxRisk` and warfarin + TMP-SMX checkers.
    """

    medication: str = Field(description="Medication name containing a methotrexate agent")
    agent: str = Field(description="Canonical methotrexate agent")
    partner_medication: str = Field(
        description="Co-prescribed trimethoprim/TMP-SMX medication name"
    )
    partner_agent: str = Field(description="Canonical trimethoprim/TMP-SMX partner agent")
    severity: Severity
    rationale: str


class TizanidineCiproRisk(BaseModel, frozen=True):
    """Tizanidine co-prescribed with a strong CYP1A2 inhibitor.

    Strong CYP1A2 inhibition elevates tizanidine exposure and intensifies
    hypotension and sedation risk. Distinct from theophylline + cipro and
    clozapine CYP1A2 checkers.
    """

    medication: str = Field(description="Medication name containing a tizanidine agent")
    agent: str = Field(description="Canonical tizanidine agent")
    partner_medication: str = Field(
        description="Co-prescribed strong CYP1A2-inhibitor medication name"
    )
    partner_agent: str = Field(description="Canonical strong CYP1A2-inhibitor partner agent")
    severity: Severity
    rationale: str


class TacrolimusCyp3a4Risk(BaseModel, frozen=True):
    """Tacrolimus + Strong CYP3A4 Inhibitor Exposure.

    Strong CYP3A4 inhibition can markedly elevate tacrolimus exposure
    and intensify nephrotoxicity / neurotoxicity risk.
    Distinct from cyclosporine interaction screens and general CYP3A4
    checkers (colchicine/fentanyl/quetiapine).
    """

    medication: str = Field(description="Medication name containing a primary agent")
    agent: str = Field(description="Canonical primary agent")
    partner_medication: str = Field(description="Co-prescribed partner medication name")
    partner_agent: str = Field(description="Canonical partner agent")
    severity: Severity
    rationale: str


class DabigatranPgpRisk(BaseModel, frozen=True):
    """Dabigatran + Strong P-gp Inhibitor Bleed Risk.

    Strong P-gp inhibition can raise dabigatran exposure and increase
    major bleeding risk.
    Distinct from DOAC + inducer thrombosis (#97) and DOAC bleeding
    intensifier checkers.
    """

    medication: str = Field(description="Medication name containing a primary agent")
    agent: str = Field(description="Canonical primary agent")
    partner_medication: str = Field(description="Co-prescribed partner medication name")
    partner_agent: str = Field(description="Canonical partner agent")
    severity: Severity
    rationale: str


class IvabradineCyp3a4Risk(BaseModel, frozen=True):
    """Ivabradine + Strong CYP3A4 Inhibitor Bradycardia.

    Strong CYP3A4 inhibition can elevate ivabradine exposure and
    precipitate severe bradycardia / conduction disturbances.
    Distinct from general QT screens and other CYP3A4 exposure checkers
    (fentanyl/quetiapine/colchicine).
    """

    medication: str = Field(description="Medication name containing a primary agent")
    agent: str = Field(description="Canonical primary agent")
    partner_medication: str = Field(description="Co-prescribed partner medication name")
    partner_agent: str = Field(description="Canonical partner agent")
    severity: Severity
    rationale: str


class SimvastatinAmiodaroneRisk(BaseModel, frozen=True):
    """Simvastatin + Amiodarone Myopathy/Rhabdomyolysis.

    Amiodarone inhibits CYP3A4-mediated simvastatin metabolism, increasing
    statin exposure and myopathy/rhabdomyolysis risk (FDA dose-limit warning).
    Distinct from statin_fibrate and digoxin_amio interaction checkers.
    """

    medication: str = Field(description="Medication name containing a primary agent")
    agent: str = Field(description="Canonical primary agent")
    partner_medication: str = Field(description="Co-prescribed partner medication name")
    partner_agent: str = Field(description="Canonical partner agent")
    severity: Severity
    rationale: str


class MidazolamCyp3a4Risk(BaseModel, frozen=True):
    """Midazolam + Strong CYP3A4 Inhibitor Sedation.

    Strong CYP3A4 inhibition can elevate midazolam exposure and prolong
    sedation / respiratory depression. Distinct from fentanyl, quetiapine,
    and ivabradine CYP3A4 exposure checkers.
    """

    medication: str = Field(description="Medication name containing a primary agent")
    agent: str = Field(description="Canonical primary agent")
    partner_medication: str = Field(description="Co-prescribed partner medication name")
    partner_agent: str = Field(description="Canonical partner agent")
    severity: Severity
    rationale: str


class CyclosporineStatinRisk(BaseModel, frozen=True):
    """Cyclosporine + Statin Myopathy / Rhabdomyolysis.

    Cyclosporine can increase statin exposure and intensify myopathy /
    rhabdomyolysis risk. Distinct from statin_fibrate, simvastatin_amiodarone,
    and digoxin_amio checkers.
    """

    medication: str = Field(description="Medication name containing a primary agent")
    agent: str = Field(description="Canonical primary agent")
    partner_medication: str = Field(description="Co-prescribed partner medication name")
    partner_agent: str = Field(description="Canonical partner agent")
    severity: Severity
    rationale: str


class SotalolQtRisk(BaseModel, frozen=True):
    """Sotalol QT-prolongation risk (alone or with QT partners).

    Sotalol carries intrinsic dose-dependent QT-prolongation and torsades risk;
    co-prescription with other QT-prolonging agents escalates severity. Distinct
    from general qt_prolongation and electrolyte_qt checkers.
    """

    medication: str = Field(description="Medication name containing a sotalol agent")
    agent: str = Field(description="Canonical sotalol agent")
    partner_medication: str = Field(
        default="",
        description="Co-prescribed QT-prolonging partner medication name, if any",
    )
    partner_agent: str = Field(
        default="",
        description="Canonical QT-prolonging partner agent; empty when sotalol alone",
    )
    severity: Severity
    rationale: str


class EscitalopramQtRisk(BaseModel, frozen=True):
    """Escitalopram / citalopram QT-prolongation risk (alone or with QT partners).

    Escitalopram and citalopram carry dose-dependent QT-prolongation risk;
    co-prescription with other QT-prolonging agents escalates severity. Distinct
    from quetiapine CYP3A4 and general qt_prolongation checkers.
    """

    medication: str = Field(
        description="Medication name containing an escitalopram/citalopram agent"
    )
    agent: str = Field(description="Canonical escitalopram or citalopram agent")
    partner_medication: str = Field(
        default="",
        description="Co-prescribed QT-prolonging partner medication name, if any",
    )
    partner_agent: str = Field(
        default="",
        description="Canonical QT-prolonging partner agent; empty when primary alone",
    )
    severity: Severity
    rationale: str


class SpironolactonePotassiumRisk(BaseModel, frozen=True):
    """Spironolactone / eplerenone + potassium hyperkalemia risk.

    Mineralocorticoid receptor antagonists plus exogenous potassium or
    potassium salt substitutes intensify hyperkalemia risk. Distinct from
    acei_potassium and acei_ksparing checkers.
    """

    medication: str = Field(description="Medication name containing an MRA agent")
    agent: str = Field(description="Canonical spironolactone or eplerenone agent")
    partner_medication: str = Field(description="Co-prescribed potassium-source medication name")
    partner_agent: str = Field(
        description="Canonical potassium-supplement or salt-substitute agent"
    )
    severity: Severity
    rationale: str


class TamoxifenCyp2d6Risk(BaseModel, frozen=True):
    """Tamoxifen + Strong CYP2D6 Inhibitor Reduced-Activation Risk.

    Tamoxifen is a prodrug activated by CYP2D6 to endoxifen. Strong CYP2D6 inhibitors
    (fluoxetine, paroxetine, bupropion, quinidine) can reduce activation and undermine
    breast-cancer endocrine therapy. Distinct from generic SSRI panels and codeine CYP2D6
    checks.
    """

    medication: str = Field(description="Medication name containing the primary agent")
    agent: str = Field(description="Canonical primary agent")
    partner_medication: str = Field(description="Co-prescribed partner medication name")
    partner_agent: str = Field(description="Canonical partner agent")
    severity: Severity
    rationale: str


class AmlodipineClarithromycinRisk(BaseModel, frozen=True):
    """Amlodipine + Clarithromycin Hypotension / Shock Risk.

    Amlodipine is a CYP3A4 substrate; clarithromycin is a strong CYP3A4 inhibitor. Co-
    prescription is linked to hospitalization for hypotension/shock in older adults.
    Distinct from simvastatin-macrolide and generic CCB panels.
    """

    medication: str = Field(description="Medication name containing the primary agent")
    agent: str = Field(description="Canonical primary agent")
    partner_medication: str = Field(description="Co-prescribed partner medication name")
    partner_agent: str = Field(description="Canonical partner agent")
    severity: Severity
    rationale: str


class MethyleneBlueSsriRisk(BaseModel, frozen=True):
    """Methylene Blue + SSRI/SNRI Serotonin Syndrome Risk.

    Intravenous methylene blue inhibits monoamine oxidase A. Co-use with serotonergic
    antidepressants can cause serotonin syndrome (FDA warning). Distinct from linezolid+SSRI
    and tramadol+SSRI checkers.
    """

    medication: str = Field(description="Medication name containing the primary agent")
    agent: str = Field(description="Canonical primary agent")
    partner_medication: str = Field(description="Co-prescribed partner medication name")
    partner_agent: str = Field(description="Canonical partner agent")
    severity: Severity
    rationale: str


class ApixabanCyp3a4Risk(BaseModel, frozen=True):
    """Apixaban + Strong CYP3A4/P-gp Inhibitor Risk.

    Apixaban is a CYP3A4/P-gp substrate; strong inhibitors (ketoconazole, itraconazole,
    ritonavir) raise exposure and bleeding risk. Distinct from dabigatran P-gp and DOAC
    inducer checkers.
    """

    medication: str = Field(description="Medication name containing the primary agent")
    agent: str = Field(description="Canonical primary agent")
    partner_medication: str = Field(description="Co-prescribed partner medication name")
    partner_agent: str = Field(description="Canonical partner agent")
    severity: Severity
    rationale: str


class PimozideCyp3a4Risk(BaseModel, frozen=True):
    """Pimozide + Strong CYP3A4 Inhibitor Risk.

    Pimozide is a CYP3A4 substrate with QT risk; strong CYP3A4 inhibitors are
    contraindicated (boxed-warning territory). Distinct from generic QT and quetiapine
    CYP3A4 checkers.
    """

    medication: str = Field(description="Medication name containing the primary agent")
    agent: str = Field(description="Canonical primary agent")
    partner_medication: str = Field(description="Co-prescribed partner medication name")
    partner_agent: str = Field(description="Canonical partner agent")
    severity: Severity
    rationale: str


class ErgotamineCyp3a4Risk(BaseModel, frozen=True):
    """Ergotamine / DHE + Strong CYP3A4 Inhibitor Risk.

    Ergot alkaloids are CYP3A4 substrates; strong inhibitors can cause ergot
    toxicity/vasospasm (contraindicated). Distinct from other CYP3A4 exposure checkers.
    """

    medication: str = Field(description="Medication name containing the primary agent")
    agent: str = Field(description="Canonical primary agent")
    partner_medication: str = Field(description="Co-prescribed partner medication name")
    partner_agent: str = Field(description="Canonical partner agent")
    severity: Severity
    rationale: str


class RifampinOcRisk(BaseModel, frozen=True):
    """Rifampin + Oral Contraceptive Efficacy Risk.

    Rifampin is a potent CYP3A4 inducer that dramatically reduces oral
    contraceptive efficacy, creating contraceptive failure risk.
    """

    medication: str = Field(description="Medication name containing the primary agent")
    agent: str = Field(description="Canonical primary agent")
    partner_medication: str = Field(description="Co-prescribed partner medication name")
    partner_agent: str = Field(description="Canonical partner agent")
    severity: Severity
    rationale: str


class PhenytoinFluconazoleRisk(BaseModel, frozen=True):
    """Phenytoin + Fluconazole CYP2C9 Inhibition Risk.

    Fluconazole inhibits CYP2C9, increasing phenytoin levels and toxicity
    risk (nystagmus, ataxia, seizures).
    """

    medication: str = Field(description="Medication name containing the primary agent")
    agent: str = Field(description="Canonical primary agent")
    partner_medication: str = Field(description="Co-prescribed partner medication name")
    partner_agent: str = Field(description="Canonical partner agent")
    severity: Severity
    rationale: str


class GentamicinVancomycinRisk(BaseModel, frozen=True):
    """Aminoglycoside + Vancomycin Additive Nephrotoxicity / Ototoxicity Risk.

    Combining aminoglycosides with vancomycin produces additive
    nephrotoxicity and ototoxicity; enhanced renal monitoring is required.
    """

    medication: str = Field(description="Medication name containing the primary agent")
    agent: str = Field(description="Canonical primary agent")
    partner_medication: str = Field(description="Co-prescribed partner medication name")
    partner_agent: str = Field(description="Canonical partner agent")
    severity: Severity
    rationale: str


class SofosbuvirAmiodaroneRisk(BaseModel, frozen=True):
    """Sofosbuvir + Amiodarone Bradycardia Risk.

    Coadministration of sofosbuvir-containing HCV regimens with amiodarone can cause serious
    symptomatic bradycardia.
    """

    medication: str = Field(description="Medication name containing the primary agent")
    agent: str = Field(description="Canonical primary agent")
    partner_medication: str = Field(description="Co-prescribed partner medication name")
    partner_agent: str = Field(description="Canonical partner agent")
    severity: Severity
    rationale: str


class RivaroxabanRifampinRisk(BaseModel, frozen=True):
    """Rivaroxaban + Rifampin Induction Risk.

    Rifampin strongly induces CYP3A4 and P-gp, reducing rivaroxaban exposure and increasing
    thrombotic risk.
    """

    medication: str = Field(description="Medication name containing the primary agent")
    agent: str = Field(description="Canonical primary agent")
    partner_medication: str = Field(description="Co-prescribed partner medication name")
    partner_agent: str = Field(description="Canonical partner agent")
    severity: Severity
    rationale: str


class FlecainideCyp2d6Risk(BaseModel, frozen=True):
    """Flecainide + Strong CYP2D6 Inhibitor Risk.

    Flecainide is a CYP2D6 substrate; strong CYP2D6 inhibitors raise
    flecainide levels and proarrhythmia risk.
    """

    medication: str = Field(description="Medication name containing the primary agent")
    agent: str = Field(description="Canonical primary agent")
    partner_medication: str = Field(description="Co-prescribed partner medication name")
    partner_agent: str = Field(description="Canonical partner agent")
    severity: Severity
    rationale: str
