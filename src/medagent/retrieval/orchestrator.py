"""Retrieval orchestrator — fans out to PubMed, drug interaction, and local KB.

Runs all three retrieval sources concurrently and merges results with
deduplication. Each source has an independent timeout so that a slow
external API cannot block the others.
"""

from __future__ import annotations

import asyncio

from medagent.config import settings
from medagent.logging_config import get_logger
from medagent.models import (
    ClinicalEntity,
    DrugInteractionWarning,
    Medication,
    RetrievedDocument,
)
from medagent.retrieval.drug_interaction import DrugInteractionClient
from medagent.retrieval.local_kb import LocalKnowledgeBase
from medagent.retrieval.pubmed import PubMedClient

logger = get_logger(__name__)


class RetrievalOrchestrator:
    """Coordinates parallel retrieval across all knowledge sources.

    Args:
        pubmed: PubMed client instance.
        drug_client: Drug interaction client instance.
        local_kb: Local knowledge base instance.
        timeout: Per-source timeout in seconds.
    """

    def __init__(
        self,
        pubmed: PubMedClient | None = None,
        drug_client: DrugInteractionClient | None = None,
        local_kb: LocalKnowledgeBase | None = None,
        timeout: int | None = None,
    ) -> None:
        self._pubmed = pubmed or PubMedClient()
        self._drug_client = drug_client or DrugInteractionClient()
        self._local_kb = local_kb or LocalKnowledgeBase()
        self._timeout = timeout or settings.agent_retrieval_timeout

    async def retrieve(
        self,
        entities: list[ClinicalEntity],
        medications: list[Medication],
    ) -> tuple[list[RetrievedDocument], list[DrugInteractionWarning]]:
        """Fan out to all retrieval sources and return merged results.

        Args:
            entities: Clinical entities extracted from patient context.
            medications: Patient medication list for interaction checking.

        Returns:
            Tuple of (deduped_docs, validated_drug_interactions).
        """
        from medagent.extraction.ner import EntityExtractor

        # Derive MeSH terms from entities for PubMed
        dummy_extractor = EntityExtractor(use_fallback=True)
        mesh_terms = dummy_extractor.get_mesh_terms(entities)

        pubmed_task = asyncio.create_task(
            self._safe_pubmed(mesh_terms)
        )
        interaction_task = asyncio.create_task(
            self._safe_interactions(medications)
        )
        kb_task = asyncio.create_task(
            self._safe_local_kb(entities)
        )

        pubmed_docs, interaction_warnings, kb_docs = await asyncio.gather(
            pubmed_task, interaction_task, kb_task
        )

        all_docs = _deduplicate_docs(pubmed_docs + kb_docs)
        logger.info(
            "retrieval_orchestration_complete",
            total_docs=len(all_docs),
            interactions=len(interaction_warnings),
        )
        return all_docs, interaction_warnings

    async def _safe_pubmed(self, mesh_terms: list[str]) -> list[RetrievedDocument]:
        """Run PubMed retrieval with timeout and error suppression."""
        try:
            return await asyncio.wait_for(
                self._pubmed.search(mesh_terms), timeout=self._timeout
            )
        except asyncio.TimeoutError:
            logger.warning("pubmed_retrieval_timeout")
            return []
        except Exception as exc:
            logger.warning("pubmed_retrieval_error", error=str(exc))
            return []

    async def _safe_interactions(
        self, medications: list[Medication]
    ) -> list[DrugInteractionWarning]:
        """Run drug interaction check with timeout and error suppression."""
        try:
            return await asyncio.wait_for(
                self._drug_client.check_interactions(medications),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("drug_interaction_timeout")
            return []
        except Exception as exc:
            logger.warning("drug_interaction_error", error=str(exc))
            return []

    async def _safe_local_kb(
        self, entities: list[ClinicalEntity]
    ) -> list[RetrievedDocument]:
        """Run local KB search with timeout and error suppression."""
        try:
            return await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, self._local_kb.search, entities
                ),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("local_kb_timeout")
            return []
        except Exception as exc:
            logger.warning("local_kb_error", error=str(exc))
            return []


def _deduplicate_docs(docs: list[RetrievedDocument]) -> list[RetrievedDocument]:
    """Remove duplicate documents by (source, doc_id), keeping highest relevance."""
    seen: dict[str, RetrievedDocument] = {}
    for doc in docs:
        key = f"{doc.source}:{doc.doc_id}"
        if key not in seen or doc.relevance_score > seen[key].relevance_score:
            seen[key] = doc
    return sorted(seen.values(), key=lambda d: d.relevance_score, reverse=True)
