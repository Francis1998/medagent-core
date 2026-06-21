"""FastAPI request/response schemas for the medagent API.

These are separate from the core domain models to allow the API contract
to evolve independently of the internal model structure.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from medagent.models import (
    ClinicalReasoning,
    DrugInteractionWarning,
    FHIRPatientContext,
    Medication,
)


class AnalyzeRequest(BaseModel):
    """Request body for POST /analyze."""

    patient_context: FHIRPatientContext = Field(
        description="FHIR-compatible patient context (PII fields must be pre-hashed)"
    )
    query: str = Field(
        description="Clinician question or reasoning task",
        min_length=5,
        max_length=2000,
    )


class AnalyzeResponse(BaseModel):
    """Response body for POST /analyze."""

    session_id: str
    result: ClinicalReasoning
    elapsed_seconds: float
    api_version: str = "0.1.0"
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class DrugInteractionRequest(BaseModel):
    """Request body for POST /drug-interactions."""

    medications: list[Medication] = Field(
        min_length=2,
        max_length=30,
        description="List of medications to check (minimum 2 required)",
    )


class DrugInteractionResponse(BaseModel):
    """Response body for POST /drug-interactions."""

    medications_checked: list[str]
    interactions_found: int
    warnings: list[DrugInteractionWarning]
    disclaimer: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str
    agent_ready: bool
    version: str = "0.1.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
