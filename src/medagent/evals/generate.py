"""Answers from medagent's real pipeline, run offline, for rubric evaluation.

:func:`generate_responses` sends each example's final user turn through
:class:`~medagent.agent.state_machine.ClinicalAgentStateMachine` (INTAKE scope
check and de-identification, entity extraction, retrieval, Bayesian reasoning,
SAFETY_CHECK confidence gating) and renders the resulting
:class:`~medagent.models.ClinicalReasoning` as the plain-text answer a reader
of ``POST /analyze`` would see (:func:`render_answer`).

The default agent (:func:`build_offline_agent`) never touches the network: the
regex entity extractor, a retriever that returns nothing (PubMed, RxNorm and
OpenFDA need network access) and a :class:`~medagent.llm.router.MedicalRouter`
without providers, so reasoning takes the engine's deterministic heuristic
fallback, exactly as medagent behaves with no LLM keys. Pass your own agent
(for example with a stub adapter) to evaluate other pipeline set-ups.

Nothing here logs prompt or answer text; the pipeline's own logs carry ids,
states and counts only (SAFETY.md §3.5).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from medagent.evals.dataset import RubricDataset, RubricExample

if TYPE_CHECKING:
    from medagent.agent.state_machine import ClinicalAgentStateMachine
    from medagent.llm.router import MedicalRouter
    from medagent.models import ClinicalQuery, ClinicalReasoning

OFFLINE_LABEL = "medagent-offline"
OFFLINE_SOURCE = "medagent pipeline (offline: regex NER, no retrieval, no LLM providers)"


class OfflineRetriever:
    """Retriever that returns no documents and no interactions, without network access."""

    async def retrieve(
        self, entities: Sequence[Any], medications: Sequence[Any]
    ) -> tuple[list[Any], list[Any]]:
        """Return ``([], [])`` for any input."""
        return [], []


def build_offline_agent(router: MedicalRouter | None = None) -> ClinicalAgentStateMachine:
    """Build medagent's state machine with offline, deterministic components.

    Args:
        router: LLM router; ``None`` uses a router without providers, so the
            reasoning engine falls back to its deterministic heuristic.

    Returns:
        A state machine that makes no network calls unless ``router`` does.
    """
    from medagent.agent.state_machine import ClinicalAgentStateMachine
    from medagent.extraction.ner import EntityExtractor
    from medagent.llm.router import MedicalRouter
    from medagent.reasoning.engine import ReasoningEngine
    from medagent.safety.scope_enforcer import ScopeEnforcer

    return ClinicalAgentStateMachine(
        extractor=EntityExtractor(use_fallback=True),
        retriever=OfflineRetriever(),  # type: ignore[arg-type]
        reasoner=ReasoningEngine(timeout_seconds=30),
        router=router if router is not None else MedicalRouter(),
        enforcer=ScopeEnforcer(),
    )


def example_to_query(example: RubricExample) -> ClinicalQuery:
    """Map a rubric conversation onto a :class:`~medagent.models.ClinicalQuery`.

    The final user turn becomes the query and chief complaint; earlier user and
    assistant turns become the clinical notes (system / developer turns are
    instructions, not clinical context, and are dropped). The patient id hash
    and session id derive from ``prompt_id`` so reruns are reproducible.

    Args:
        example: The rubric example.

    Returns:
        The query the pipeline answers.
    """
    from medagent.models import ClinicalQuery, FHIRPatientContext

    history = [
        f"{message.role}: {message.content}"
        for message in example.prompt[:-1]
        if message.role in ("user", "assistant")
    ]
    digest = hashlib.sha256(f"rubric-eval:{example.prompt_id}".encode()).hexdigest()
    context = FHIRPatientContext(
        patient_id_hash=digest,
        chief_complaint=example.question,
        clinical_notes="\n".join(history),
    )
    return ClinicalQuery(
        session_id=f"rubric-eval-{example.prompt_id}",
        patient_context=context,
        query=example.question,
    )


def _sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "!", "?")) else f"{text}."


def render_answer(result: ClinicalReasoning) -> str:
    """Render a pipeline result as the plain-text answer that gets graded.

    Every user-visible field of the ``/analyze`` result is included, in order:
    ranked hypotheses, overall confidence, drug-interaction warnings,
    uncertainty flags, the escalation notice, recommended next steps and the
    mandatory disclaimer. Run metadata (ids, timings) is left out so the text
    is reproducible.

    Args:
        result: Output of ``ClinicalAgentStateMachine.run``.

    Returns:
        One line per item, newline-separated.
    """
    from medagent.safety.disclaimer import ESCALATION_MESSAGE

    lines: list[str] = []
    if result.ranked_hypotheses:
        lines.append("Ranked research hypotheses (for clinician review, not a diagnosis):")
        for rank, hypothesis in enumerate(result.ranked_hypotheses, 1):
            line = f"{rank}. {hypothesis.label} (Bayesian score {hypothesis.bayesian_score:.2f})"
            if hypothesis.uncertainty_note:
                line += f": {_sentence(hypothesis.uncertainty_note)}"
            lines.append(line)
    else:
        lines.append("No research hypotheses were generated.")
    lines.append(f"Overall confidence: {result.overall_confidence:.2f}.")
    for warning in result.drug_interactions_flagged:
        lines.append(
            f"Drug interaction flagged: {warning.drug_a} + {warning.drug_b} "
            f"({warning.severity.value}): {_sentence(warning.clinical_consequence)}"
        )
    if result.uncertainty_flags:
        lines.append("Uncertainty flags:")
        lines.extend(f"- {_sentence(flag)}" for flag in result.uncertainty_flags)
    if result.escalated:
        lines.append(ESCALATION_MESSAGE)
    if result.recommended_next_steps:
        lines.append("Recommended next steps:")
        lines.extend(f"- {_sentence(step)}" for step in result.recommended_next_steps)
    lines.append(result.disclaimer.strip())
    return "\n".join(lines)


async def generate_responses(
    dataset: RubricDataset, agent: ClinicalAgentStateMachine | None = None
) -> dict[str, str]:
    """Answer every example with medagent's pipeline, one run per example.

    Args:
        dataset: The rubric dataset.
        agent: State machine to run; ``None`` uses :func:`build_offline_agent`.

    Returns:
        ``prompt_id`` → rendered answer, in dataset order.
    """
    runner = agent if agent is not None else build_offline_agent()
    responses: dict[str, str] = {}
    for example in dataset.examples:
        result = await runner.run(example_to_query(example))
        responses[example.prompt_id] = render_answer(result)
    return responses
