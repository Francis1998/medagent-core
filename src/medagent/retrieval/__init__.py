"""Retrieval module — PubMed, DrugBank/OpenFDA, and local knowledge base."""

from medagent.retrieval.drug_interaction import DrugInteractionClient
from medagent.retrieval.local_kb import LocalKnowledgeBase, build_sample_index
from medagent.retrieval.orchestrator import RetrievalOrchestrator
from medagent.retrieval.pubmed import PubMedClient

__all__ = [
    "DrugInteractionClient",
    "LocalKnowledgeBase",
    "PubMedClient",
    "RetrievalOrchestrator",
    "build_sample_index",
]
