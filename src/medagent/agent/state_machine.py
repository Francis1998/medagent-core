"""Clinical reasoning agent state machine.

Implements the Observe → Decide → Act loop as an explicit finite state machine:
    INTAKE → ENTITY_EXTRACTION → KNOWLEDGE_RETRIEVAL → REASONING
           → SAFETY_CHECK → OUTPUT | ESCALATE

Each transition is logged and persisted to the durable audit store.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from medagent.logging_config import get_logger
from medagent.models import AgentState, ClinicalQuery, ClinicalReasoning

if TYPE_CHECKING:
    from medagent.extraction.ner import EntityExtractor
    from medagent.llm.router import MedicalRouter
    from medagent.reasoning.engine import ReasoningEngine
    from medagent.retrieval.orchestrator import RetrievalOrchestrator
    from medagent.safety.scope_enforcer import ScopeEnforcer

logger = get_logger(__name__)


@dataclass
class RunContext:
    """Mutable context threaded through each state transition.

    Accumulates intermediate results so that every state can read
    outputs produced by previous states without global side effects.
    """

    query: ClinicalQuery
    current_state: AgentState = AgentState.INTAKE
    state_history: list[AgentState] = field(default_factory=list)
    intermediate: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.monotonic)


class StateMachineError(Exception):
    """Raised when a state transition is invalid or a state handler fails fatally."""


class ClinicalAgentStateMachine:
    """Explicit finite state machine driving one clinical reasoning run.

    Args:
        extractor: Biomedical entity extractor (scispaCy NER).
        retriever: Hybrid knowledge retrieval orchestrator.
        reasoner: Bayesian reasoning engine.
        router: Multi-LLM medical routing layer.
        enforcer: Safety scope enforcer.
        confidence_threshold: Minimum score before triggering ESCALATE.
    """

    VALID_TRANSITIONS: ClassVar[dict[AgentState, set[AgentState]]] = {
        AgentState.INTAKE: {AgentState.ENTITY_EXTRACTION, AgentState.ERROR},
        AgentState.ENTITY_EXTRACTION: {AgentState.KNOWLEDGE_RETRIEVAL, AgentState.ERROR},
        AgentState.KNOWLEDGE_RETRIEVAL: {AgentState.REASONING, AgentState.ERROR},
        AgentState.REASONING: {AgentState.SAFETY_CHECK, AgentState.ERROR},
        AgentState.SAFETY_CHECK: {
            AgentState.OUTPUT,
            AgentState.ESCALATE,
            AgentState.ERROR,
        },
        AgentState.OUTPUT: set(),
        AgentState.ESCALATE: set(),
        AgentState.ERROR: set(),
    }

    def __init__(
        self,
        extractor: EntityExtractor,
        retriever: RetrievalOrchestrator,
        reasoner: ReasoningEngine,
        router: MedicalRouter,
        enforcer: ScopeEnforcer,
        confidence_threshold: float = 0.6,
    ) -> None:
        self._extractor = extractor
        self._retriever = retriever
        self._reasoner = reasoner
        self._router = router
        self._enforcer = enforcer
        self._confidence_threshold = confidence_threshold

    def _transition(self, ctx: RunContext, next_state: AgentState) -> None:
        """Validate and apply a state transition, updating ctx in place.

        Args:
            ctx: Current run context.
            next_state: Target state to transition to.

        Raises:
            StateMachineError: When the transition is not in VALID_TRANSITIONS.
        """
        allowed = self.VALID_TRANSITIONS.get(ctx.current_state, set())
        if next_state not in allowed:
            raise StateMachineError(
                f"Invalid transition: {ctx.current_state} → {next_state}. Allowed: {allowed}"
            )
        logger.info(
            "state_transition",
            session_id=ctx.query.session_id,
            from_state=ctx.current_state.value,
            to_state=next_state.value,
            elapsed_ms=round((time.monotonic() - ctx.start_time) * 1000),
        )
        ctx.state_history.append(ctx.current_state)
        ctx.current_state = next_state

    async def run(self, query: ClinicalQuery) -> ClinicalReasoning:
        """Execute the full agentic loop for a clinical query.

        Args:
            query: Validated, PII-sanitized clinical query.

        Returns:
            Structured ClinicalReasoning output.
        """
        ctx = RunContext(query=query)
        logger.info(
            "agent_run_start",
            session_id=query.session_id,
            inputs_hash=query.inputs_hash,
        )

        try:
            await self._handle_intake(ctx)
            await self._handle_entity_extraction(ctx)
            await self._handle_knowledge_retrieval(ctx)
            await self._handle_reasoning(ctx)
            result = await self._handle_safety_check(ctx)
        except StateMachineError as exc:
            logger.error("state_machine_error", error=str(exc), session_id=query.session_id)
            ctx.errors.append(str(exc))
            ctx.current_state = AgentState.ERROR
            result = self._build_error_output(ctx)
        except Exception as exc:
            logger.exception("agent_unexpected_error", session_id=query.session_id)
            ctx.errors.append(f"Unexpected: {exc}")
            ctx.current_state = AgentState.ERROR
            result = self._build_error_output(ctx)

        wall_time = round(time.monotonic() - ctx.start_time, 3)
        logger.info(
            "agent_run_complete",
            session_id=query.session_id,
            state=ctx.current_state.value,
            wall_time_seconds=wall_time,
            escalated=result.escalated,
        )
        # Inject wall time via reconstruction (models are frozen)
        return result.model_copy(
            update={"wall_time_seconds": wall_time, "inputs_hash": query.inputs_hash}
        )

    # ------------------------------------------------------------------
    # State handlers
    # ------------------------------------------------------------------

    async def _handle_intake(self, ctx: RunContext) -> None:
        """INTAKE: validate scope and log run start."""
        self._enforcer.check_query_in_scope(ctx.query.query)
        self._transition(ctx, AgentState.ENTITY_EXTRACTION)

    async def _handle_entity_extraction(self, ctx: RunContext) -> None:
        """ENTITY_EXTRACTION: run scispaCy NER on clinical text."""
        complaint = ctx.query.patient_context.chief_complaint
        notes = ctx.query.patient_context.clinical_notes
        text = f"{complaint}\n{notes}"
        entities = await self._extractor.extract(text)
        ctx.intermediate["entities"] = entities
        logger.info(
            "entities_extracted",
            session_id=ctx.query.session_id,
            count=len(entities),
        )
        self._transition(ctx, AgentState.KNOWLEDGE_RETRIEVAL)

    async def _handle_knowledge_retrieval(self, ctx: RunContext) -> None:
        """KNOWLEDGE_RETRIEVAL: fetch relevant docs from PubMed, OpenFDA, local KB."""
        entities = ctx.intermediate.get("entities", [])
        medications = ctx.query.patient_context.medications
        docs, interactions = await self._retriever.retrieve(
            entities=entities,
            medications=medications,
        )
        ctx.intermediate["docs"] = docs
        ctx.intermediate["interactions"] = interactions
        logger.info(
            "retrieval_complete",
            session_id=ctx.query.session_id,
            doc_count=len(docs),
            interaction_count=len(interactions),
        )
        self._transition(ctx, AgentState.REASONING)

    async def _handle_reasoning(self, ctx: RunContext) -> None:
        """REASONING: produce ranked hypotheses with Bayesian scores and evidence chains."""
        hypotheses = await self._reasoner.reason(
            query=ctx.query,
            entities=ctx.intermediate.get("entities", []),
            docs=ctx.intermediate.get("docs", []),
            router=self._router,
        )
        ctx.intermediate["hypotheses"] = hypotheses
        logger.info(
            "reasoning_complete",
            session_id=ctx.query.session_id,
            hypotheses_count=len(hypotheses),
        )
        self._transition(ctx, AgentState.SAFETY_CHECK)

    async def _handle_safety_check(self, ctx: RunContext) -> ClinicalReasoning:
        """SAFETY_CHECK: confidence gating → OUTPUT or ESCALATE."""
        from medagent.safety.disclaimer import MANDATORY_DISCLAIMER

        hypotheses = ctx.intermediate.get("hypotheses", [])
        docs = ctx.intermediate.get("docs", [])
        entities = ctx.intermediate.get("entities", [])
        interactions = ctx.intermediate.get("interactions", [])

        # Compute overall confidence as weighted mean of top-3 hypotheses
        top_scores = sorted([h.bayesian_score for h in hypotheses], reverse=True)[:3]
        overall_confidence = sum(top_scores) / max(len(top_scores), 1)

        uncertainty_flags: list[str] = []
        escalated = False

        if not hypotheses:
            uncertainty_flags.append("No hypotheses generated — human review required")
            escalated = True
        elif overall_confidence < self._confidence_threshold:
            uncertainty_flags.append(
                f"Overall confidence {overall_confidence:.2f} below threshold "
                f"{self._confidence_threshold:.2f} — human review required"
            )
            escalated = True

        if self._has_contradictory_evidence(hypotheses):
            uncertainty_flags.append("Contradictory evidence detected — automatic escalation")
            escalated = True

        next_state = AgentState.ESCALATE if escalated else AgentState.OUTPUT
        self._transition(ctx, next_state)

        next_steps: list[str] = []
        if escalated:
            next_steps = [
                "Refer to a board-certified clinician for further evaluation.",
                "Consider additional diagnostic workup to resolve ambiguous findings.",
            ]
        else:
            next_steps = [
                "Review ranked hypotheses with the clinical team.",
                "Validate drug interaction warnings against the patient's current medication list.",
            ]

        return ClinicalReasoning(
            session_id=ctx.query.session_id,
            query=ctx.query.query,
            state_reached=next_state,
            ranked_hypotheses=hypotheses,
            drug_interactions_flagged=interactions,
            overall_confidence=overall_confidence,
            uncertainty_flags=uncertainty_flags,
            escalated=escalated,
            evidence_chain=docs,
            entities_extracted=entities,
            recommended_next_steps=next_steps,
            disclaimer=MANDATORY_DISCLAIMER,
        )

    def _has_contradictory_evidence(self, hypotheses: list[Any]) -> bool:
        """Detect contradictory evidence across the top hypotheses.

        A simple heuristic: if the top hypothesis has both strong FOR and
        strong AGAINST evidence, flag as contradictory.
        """
        for hyp in hypotheses[:2]:
            strong_for = any(e.strength >= 0.8 for e in hyp.evidence_for)
            strong_against = any(e.strength >= 0.8 for e in hyp.evidence_against)
            if strong_for and strong_against:
                return True
        return False

    def _build_error_output(self, ctx: RunContext) -> ClinicalReasoning:
        """Construct a safe error output when the state machine fails."""
        from medagent.safety.disclaimer import MANDATORY_DISCLAIMER

        return ClinicalReasoning(
            session_id=ctx.query.session_id,
            query=ctx.query.query,
            state_reached=AgentState.ERROR,
            overall_confidence=0.0,
            escalated=True,
            uncertainty_flags=[f"Agent error: {e}" for e in ctx.errors],
            recommended_next_steps=["Contact support. Consult a clinician directly."],
            disclaimer=MANDATORY_DISCLAIMER,
        )
