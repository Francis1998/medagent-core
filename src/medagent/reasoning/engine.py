"""Reasoning engine — produces ranked differential hypotheses via LLM + Bayesian scoring.

The engine:
1. Constructs a structured prompt from entities and retrieved documents.
2. Routes to the appropriate LLM via MedicalRouter.
3. Parses the structured LLM response into Hypothesis objects.
4. Applies Bayesian scoring and ranks hypotheses.
5. Flags low-confidence results for escalation.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import TYPE_CHECKING, Any

from medagent.logging_config import get_logger
from medagent.models import (
    ClinicalEntity,
    ClinicalQuery,
    EvidenceItem,
    Hypothesis,
    RetrievedDocument,
)
from medagent.reasoning.bayesian import rank_hypotheses

if TYPE_CHECKING:
    from medagent.llm.router import MedicalRouter

logger = get_logger(__name__)

_REASONING_PROMPT_TEMPLATE = """You are a clinical decision support AI assistant.
Your role is to assist clinicians in generating differential diagnoses.
You MUST NOT provide direct treatment prescriptions.

## Patient Context
Chief Complaint: {chief_complaint}
Identified Entities: {entities}

## Retrieved Evidence
{evidence_snippets}

## Task
Generate a differential diagnosis with up to 5 ranked hypotheses.
For each hypothesis, list:
- evidence_for: supporting points (cite snippet indices if possible)
- evidence_against: contradicting points
- uncertainty_note: any important caveat

Respond ONLY with valid JSON matching this schema:
{{
  "hypotheses": [
    {{
      "label": "string",
      "icd_code": "string or null",
      "evidence_for": [{{"statement": "string", "strength": 0.0-1.0}}],
      "evidence_against": [{{"statement": "string", "strength": 0.0-1.0}}],
      "uncertainty_note": "string or null"
    }}
  ]
}}
"""


class ReasoningEngine:
    """LLM-backed clinical reasoning engine with Bayesian hypothesis ranking.

    Args:
        timeout_seconds: Hard timeout for the LLM reasoning call.
    """

    def __init__(self, timeout_seconds: int = 90) -> None:
        self._timeout = timeout_seconds

    async def reason(
        self,
        query: ClinicalQuery,
        entities: list[ClinicalEntity],
        docs: list[RetrievedDocument],
        router: MedicalRouter,
    ) -> list[Hypothesis]:
        """Produce ranked differential hypotheses for a clinical query.

        Args:
            query: The clinical query with patient context.
            entities: Extracted biomedical entities.
            docs: Retrieved supporting documents.
            router: Multi-LLM medical routing layer.

        Returns:
            Ranked list of Hypothesis objects with Bayesian scores.
        """
        prompt = self._build_prompt(query, entities, docs)

        try:
            raw_response = await asyncio.wait_for(
                router.route_differential(prompt),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "reasoning_timeout",
                session_id=query.session_id,
                timeout_seconds=self._timeout,
            )
            return self._fallback_hypotheses(entities)
        except Exception as exc:
            logger.warning("reasoning_error", error=str(exc), session_id=query.session_id)
            return self._fallback_hypotheses(entities)

        hypotheses = self._parse_llm_response(raw_response, docs)
        ranked = rank_hypotheses(hypotheses)

        logger.info(
            "hypotheses_ranked",
            session_id=query.session_id,
            count=len(ranked),
            top_score=ranked[0].bayesian_score if ranked else None,
        )
        return ranked

    def _build_prompt(
        self,
        query: ClinicalQuery,
        entities: list[ClinicalEntity],
        docs: list[RetrievedDocument],
    ) -> str:
        """Construct the structured reasoning prompt."""
        entity_str = ", ".join(f"{e.text} ({e.label})" for e in entities[:15])

        evidence_lines: list[str] = []
        for i, doc in enumerate(docs[:5]):
            evidence_lines.append(f"[{i}] {doc.title}: {doc.snippet}")
        evidence_str = (
            "\n".join(evidence_lines) if evidence_lines else "No external evidence retrieved."
        )

        return _REASONING_PROMPT_TEMPLATE.format(
            chief_complaint=query.patient_context.chief_complaint,
            entities=entity_str or "None detected",
            evidence_snippets=evidence_str,
        )

    def _parse_llm_response(
        self,
        response: str,
        docs: list[RetrievedDocument],
    ) -> list[Hypothesis]:
        """Parse JSON response from the LLM into Hypothesis objects.

        Falls back to an empty list on any parse failure, which triggers
        the fallback path in the state machine.
        """
        # Strip markdown code fences if present. The language tag after the
        # opening fence is matched generically and case-insensitively: models
        # emit ```json, ```JSON, or a bare ``` fence, and a case-sensitive
        # ``(?:json)?`` left an uppercase "JSON" tag in the payload, breaking
        # json.loads and silently dropping every hypothesis.
        response = re.sub(r"```[a-zA-Z0-9]*", "", response).strip().rstrip("`").strip()

        try:
            data: dict[str, Any] = json.loads(response)
        except json.JSONDecodeError as exc:
            logger.warning("reasoning_parse_error", error=str(exc), snippet=response[:200])
            return []

        raw_hyps = data.get("hypotheses", [])
        if not isinstance(raw_hyps, list):
            return []

        hypotheses: list[Hypothesis] = []
        doc_ids = [d.doc_id for d in docs]
        source_doc_id = doc_ids[0] if doc_ids else None

        for raw in raw_hyps[:5]:
            if not isinstance(raw, dict):
                continue
            try:
                evidence_for = self._parse_evidence(
                    raw.get("evidence_for", []), "FOR", source_doc_id
                )
                evidence_against = self._parse_evidence(
                    raw.get("evidence_against", []), "AGAINST", source_doc_id
                )
                hyp = Hypothesis(
                    label=raw.get("label", "Unknown"),
                    icd_code=raw.get("icd_code"),
                    evidence_for=evidence_for,
                    evidence_against=evidence_against,
                    uncertainty_note=raw.get("uncertainty_note"),
                )
                hypotheses.append(hyp)
            except Exception as exc:
                logger.warning("hypothesis_parse_error", error=str(exc))

        return hypotheses

    @staticmethod
    def _parse_evidence(
        raw_items: object,
        direction: str,
        source_doc_id: str | None,
    ) -> list[EvidenceItem]:
        """Parse an LLM ``evidence_for``/``evidence_against`` list tolerantly.

        The prompt asks for a list of ``{"statement": ..., "strength": ...}``
        objects, but models frequently emit each evidence item as a bare string
        instead. The previous ``e.get("statement")`` assumed every item was a
        dict, so a string item raised ``AttributeError`` that was caught one
        level up and silently discarded the *entire* hypothesis. Both shapes are
        now supported: a bare string becomes the statement with a neutral default
        strength, and a malformed or out-of-range strength is coerced/clamped
        rather than dropping the item.

        Args:
            raw_items: The raw ``evidence_for``/``evidence_against`` value.
            direction: ``"FOR"`` or ``"AGAINST"``.
            source_doc_id: Optional source document id to attribute evidence to.

        Returns:
            Parsed evidence items; items without a usable statement are skipped.
        """
        if not isinstance(raw_items, list):
            return []
        items: list[EvidenceItem] = []
        for entry in raw_items:
            if isinstance(entry, str):
                statement = entry.strip()
                strength = 0.5
            elif isinstance(entry, dict):
                statement = str(entry.get("statement", "")).strip()
                strength = ReasoningEngine._coerce_strength(entry.get("strength", 0.5))
            else:
                continue
            if not statement:
                continue
            items.append(
                EvidenceItem(
                    direction=direction,
                    statement=statement,
                    strength=strength,
                    source_doc_id=source_doc_id,
                    source_label="retrieved_evidence",
                )
            )
        return items

    @staticmethod
    def _coerce_strength(value: object) -> float:
        """Coerce a raw strength value to a float clamped to ``[0.0, 1.0]``.

        Args:
            value: Raw strength from the LLM (may be a number, numeric string, or
                out of range).

        Returns:
            A float within ``[0.0, 1.0]``; defaults to ``0.5`` when uncoercible.
        """
        try:
            strength = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, strength))

    def _fallback_hypotheses(self, entities: list[ClinicalEntity]) -> list[Hypothesis]:
        """Return a minimal fallback hypothesis when LLM reasoning fails."""
        diseases = [e for e in entities if e.label == "DISEASE"]
        if diseases:
            return [
                Hypothesis(
                    label=diseases[0].text,
                    evidence_for=[
                        EvidenceItem(
                            direction="FOR",
                            statement=f"Entity '{diseases[0].text}' identified in clinical text",
                            strength=0.4,
                        )
                    ],
                    evidence_against=[],
                    uncertainty_note="Reasoning engine fallback — LLM call failed",
                )
            ]
        return []
