"""FastAPI application entry point.

Provides three endpoints:
  POST /analyze           — full clinical reasoning run
  POST /drug-interactions — targeted drug interaction check
  GET  /health            — readiness probe
"""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from medagent.agent.audit import persist_run
from medagent.agent.state_machine import ClinicalAgentStateMachine
from medagent.api.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    DrugInteractionRequest,
    DrugInteractionResponse,
    HealthResponse,
)
from medagent.config import settings
from medagent.extraction.ner import EntityExtractor
from medagent.llm.router import MedicalRouter
from medagent.logging_config import configure_logging, get_logger
from medagent.models import ClinicalQuery
from medagent.reasoning.engine import ReasoningEngine
from medagent.retrieval.drug_interaction import DrugInteractionClient
from medagent.retrieval.local_kb import LocalKnowledgeBase, build_sample_index
from medagent.retrieval.orchestrator import RetrievalOrchestrator
from medagent.retrieval.pubmed import PubMedClient
from medagent.safety.scope_enforcer import ScopeEnforcer

logger = get_logger(__name__)

# Module-level agent singleton (initialised in lifespan)
_agent: ClinicalAgentStateMachine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialise shared resources on startup and clean up on shutdown."""
    global _agent
    configure_logging(settings.log_level)
    logger.info("medagent_startup", version="0.1.0")

    # Build sample KB index if missing (dev convenience)
    build_sample_index()

    extractor = EntityExtractor(use_fallback=True)  # fallback mode avoids spaCy dependency
    retriever = RetrievalOrchestrator(
        pubmed=PubMedClient(),
        drug_client=DrugInteractionClient(),
        local_kb=LocalKnowledgeBase(),
    )
    reasoner = ReasoningEngine(timeout_seconds=settings.agent_reasoning_timeout)
    router = MedicalRouter.from_settings()
    enforcer = ScopeEnforcer()

    _agent = ClinicalAgentStateMachine(
        extractor=extractor,
        retriever=retriever,
        reasoner=reasoner,
        router=router,
        enforcer=enforcer,
        confidence_threshold=settings.agent_confidence_threshold,
    )

    logger.info("medagent_ready")
    yield
    logger.info("medagent_shutdown")


app = FastAPI(
    title="medagent-core",
    description=(
        "Auditable biomedical AI decision support agent — multi-hop clinical reasoning, "
        "drug interaction detection, and safety-first agentic architecture. "
        "RESEARCH USE ONLY — NOT FDA-cleared."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a safe JSON error response for all unhandled exceptions."""
    logger.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Please try again.",
        },
    )


@app.get("/health", response_model=HealthResponse, tags=["Operations"])
async def health() -> HealthResponse:
    """Readiness probe.

    Returns:
        JSON with status=ok and the current timestamp.
    """
    return HealthResponse(status="ok", agent_ready=_agent is not None)


@app.post("/analyze", response_model=AnalyzeResponse, tags=["Clinical Reasoning"])
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """Run a full clinical reasoning agent pass on the submitted patient context.

    The agent executes the full INTAKE → ENTITY_EXTRACTION → KNOWLEDGE_RETRIEVAL
    → REASONING → SAFETY_CHECK → OUTPUT | ESCALATE state machine.

    Args:
        request: Structured clinical query with FHIR-compatible patient context.

    Returns:
        ClinicalReasoning output with ranked hypotheses, drug interactions,
        confidence scores, evidence chain, and mandatory disclaimer.

    Raises:
        HTTPException 503: If the agent has not been initialised.
        HTTPException 400: If the request scope is violated.
    """
    if _agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent not ready. Please retry in a moment.",
        )

    start = time.monotonic()

    query = ClinicalQuery(
        patient_context=request.patient_context,
        query=request.query,
    )

    try:
        import async_timeout  # noqa: F401
    except ImportError:
        pass

    import asyncio

    try:
        result = await asyncio.wait_for(
            _agent.run(query),
            timeout=settings.agent_total_timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail=f"Agent run exceeded {settings.agent_total_timeout_seconds}s hard timeout.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # Persist to audit log (non-blocking background task)
    _audit_task = asyncio.ensure_future(persist_run(result))
    _audit_task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

    return AnalyzeResponse(
        session_id=result.session_id,
        result=result,
        elapsed_seconds=round(time.monotonic() - start, 3),
    )


@app.post(
    "/drug-interactions",
    response_model=DrugInteractionResponse,
    tags=["Drug Interactions"],
)
async def drug_interactions(request: DrugInteractionRequest) -> DrugInteractionResponse:
    """Check drug-drug interactions for a supplied medication list.

    Each interaction is validated against at least 2 independent data sources
    before being included in the response. Unvalidated interactions are silently
    suppressed per the safety invariant.

    Args:
        request: List of medications to check.

    Returns:
        Validated drug interaction warnings.
    """
    client = DrugInteractionClient()
    try:
        warnings = await client.check_interactions(request.medications)
    except Exception as exc:
        logger.error("drug_interaction_endpoint_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Drug interaction service temporarily unavailable.",
        ) from exc

    return DrugInteractionResponse(
        medications_checked=[m.name for m in request.medications],
        interactions_found=len(warnings),
        warnings=warnings,
        disclaimer=(
            "Drug interaction data is sourced from public APIs and has NOT been reviewed "
            "by a pharmacist. Always verify with a clinical pharmacist before any "
            "clinical decision."
        ),
    )
