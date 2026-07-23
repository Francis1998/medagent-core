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
