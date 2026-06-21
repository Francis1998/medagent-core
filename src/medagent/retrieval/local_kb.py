"""Local biomedical knowledge base with hybrid BM25 + dense retrieval.

Implements the same hybrid retrieval strategy as the router-level KB:
1. BM25 keyword scoring (rank-bm25)
2. Dense cosine similarity via numpy dot product (UMLS/BioWordVec embeddings)
3. Linear interpolation reranking: score = α·bm25 + (1-α)·dense

The knowledge base is built from a JSONL file (one doc per line) and an
optional pre-computed embedding matrix. When embeddings are unavailable the
system falls back to BM25-only ranking.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray
from rank_bm25 import BM25Okapi

from medagent.logging_config import get_logger
from medagent.models import ClinicalEntity, RetrievedDocument

logger = get_logger(__name__)

_ALPHA = 0.5  # weight of BM25 vs. dense; 0 = pure dense, 1 = pure BM25


class LocalKnowledgeBase:
    """In-memory biomedical knowledge base with hybrid retrieval.

    Args:
        index_path: Directory containing ``docs.jsonl`` and optionally
            ``embeddings.npy`` and ``embedding_index.json``.
        top_k: Number of documents to return per query.
        alpha: BM25 weight in hybrid scoring (0–1). Dense weight = 1-alpha.
    """

    def __init__(
        self,
        index_path: str = "./data/kb_index/",
        top_k: int = 5,
        alpha: float = _ALPHA,
    ) -> None:
        self._index_path = Path(index_path)
        self._top_k = top_k
        self._alpha = alpha

        self._docs: list[dict[str, Any]] = []
        self._tokenized: list[list[str]] = []
        self._bm25: BM25Okapi | None = None
        self._embeddings: NDArray[Any] | None = None  # shape: (N, dim)
        self._loaded = False

    def load(self) -> None:
        """Load documents and embeddings from disk.

        Silently skips loading if the index directory does not exist so that
        the rest of the pipeline remains operational without a local KB.
        """
        docs_path = self._index_path / "docs.jsonl"
        if not docs_path.exists():
            logger.warning(
                "local_kb_not_found",
                path=str(docs_path),
                message="Local KB unavailable; hybrid retrieval will skip dense component",
            )
            self._loaded = True
            return

        with docs_path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        self._docs.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        self._tokenized = [
            _tokenize(d.get("title", "") + " " + d.get("text", "")) for d in self._docs
        ]
        if self._tokenized:
            self._bm25 = BM25Okapi(self._tokenized)

        emb_path = self._index_path / "embeddings.npy"
        if emb_path.exists():
            try:
                self._embeddings = np.load(str(emb_path))
                logger.info(
                    "kb_embeddings_loaded",
                    shape=self._embeddings.shape,
                )
            except Exception as exc:
                logger.warning("kb_embedding_load_error", error=str(exc))

        logger.info("local_kb_loaded", doc_count=len(self._docs))
        self._loaded = True

    def search(
        self,
        entities: list[ClinicalEntity],
        query_text: str = "",
    ) -> list[RetrievedDocument]:
        """Hybrid BM25 + dense search over the local knowledge base.

        Args:
            entities: Extracted clinical entities used to form the query.
            query_text: Optional additional free-text query.

        Returns:
            Top-k RetrievedDocument objects ranked by hybrid score.
        """
        if not self._loaded:
            self.load()

        if not self._docs or self._bm25 is None:
            return []

        # Build query string from entity texts + free text
        query_tokens = _tokenize(" ".join(e.text for e in entities) + " " + query_text)
        if not query_tokens:
            return []

        bm25_scores = np.array(self._bm25.get_scores(query_tokens))
        bm25_norm = _minmax_normalize(bm25_scores)

        if self._embeddings is not None:
            query_vec = self._mean_bow_embedding(query_tokens)
            if query_vec is not None:
                cosine_scores = self._embeddings.dot(query_vec) / (
                    np.linalg.norm(self._embeddings, axis=1) * np.linalg.norm(query_vec) + 1e-9
                )
                dense_norm = _minmax_normalize(cosine_scores)
                hybrid_scores = self._alpha * bm25_norm + (1 - self._alpha) * dense_norm
            else:
                hybrid_scores = bm25_norm
        else:
            hybrid_scores = bm25_norm

        top_indices = np.argsort(hybrid_scores)[::-1][: self._top_k]

        results: list[RetrievedDocument] = []
        for idx in top_indices:
            doc = self._docs[int(idx)]
            score = float(hybrid_scores[int(idx)])
            if score < 0.01:
                continue
            try:
                results.append(
                    RetrievedDocument(
                        source="local_kb",
                        doc_id=doc.get("id", str(idx)),
                        title=doc.get("title", "Untitled"),
                        snippet=doc.get("text", "")[:400],
                        url=doc.get("url"),
                        relevance_score=round(score, 4),
                        mesh_terms=doc.get("mesh_terms", []),
                        published_date=doc.get("published_date"),
                    )
                )
            except Exception as exc:
                logger.warning("kb_doc_parse_error", error=str(exc), idx=idx)

        return results

    def _mean_bow_embedding(self, tokens: list[str]) -> NDArray[Any] | None:
        """Placeholder for word-vector lookup.

        In a full deployment this would look up each token in a pre-loaded
        BioWordVec model. Here we return None to trigger BM25-only fallback.
        """
        return None


def _tokenize(text: str) -> list[str]:
    """Lowercase tokeniser that splits on whitespace and strips punctuation."""
    import re

    return re.findall(r"[a-z0-9]+", text.lower())


def _minmax_normalize(arr: NDArray[Any]) -> NDArray[Any]:
    """Normalize an array to [0, 1] using min-max scaling."""
    arr_min = arr.min()
    arr_max = arr.max()
    if math.isclose(arr_max - arr_min, 0.0):
        return np.zeros_like(arr)
    return cast(NDArray[Any], (arr - arr_min) / (arr_max - arr_min))


def build_sample_index(output_dir: str = "./data/kb_index/") -> None:
    """Create a minimal sample knowledge base index for testing.

    Args:
        output_dir: Directory to write ``docs.jsonl`` into.
    """
    os.makedirs(output_dir, exist_ok=True)
    sample_docs = [
        {
            "id": "kb_001",
            "title": "Metformin and Renal Function",
            "text": (
                "Metformin is contraindicated in patients with eGFR < 30 mL/min/1.73m² "
                "due to risk of lactic acidosis. Regular monitoring of renal function is "
                "recommended for all patients on metformin therapy."
            ),
            "mesh_terms": ["Metformin", "Renal Insufficiency", "Lactic Acidosis"],
            "url": "https://pubmed.ncbi.nlm.nih.gov/sample1/",
        },
        {
            "id": "kb_002",
            "title": "Warfarin Drug Interactions",
            "text": (
                "Warfarin has a narrow therapeutic index and interacts with numerous drugs. "
                "NSAIDs increase bleeding risk. Amiodarone, fluconazole, and trimethoprim "
                "significantly potentiate warfarin anticoagulant effect via CYP2C9 inhibition."
            ),
            "mesh_terms": ["Warfarin", "Drug Interactions", "Anticoagulants"],
            "url": "https://pubmed.ncbi.nlm.nih.gov/sample2/",
        },
        {
            "id": "kb_003",
            "title": "Type 2 Diabetes Mellitus — Diagnostic Criteria",
            "text": (
                "T2DM is diagnosed by: fasting plasma glucose ≥126 mg/dL, 2-h plasma glucose "
                "≥200 mg/dL during OGTT, HbA1c ≥6.5%, or random glucose ≥200 with symptoms. "
                "Repeat testing is required unless the presentation is unequivocal."
            ),
            "mesh_terms": ["Diabetes Mellitus, Type 2", "Blood Glucose", "HbA1c"],
        },
        {
            "id": "kb_004",
            "title": "Acute Myocardial Infarction — Biomarkers",
            "text": (
                "Cardiac troponin I and T are the preferred biomarkers for AMI diagnosis. "
                "Levels rise within 3–6 hours of symptom onset, peak at 18–24 hours, and "
                "return to baseline over 10–14 days. High-sensitivity assays improve early "
                "rule-out at 0/1 hour and 0/2 hour protocols."
            ),
            "mesh_terms": ["Myocardial Infarction", "Troponin", "Biomarkers"],
        },
        {
            "id": "kb_005",
            "title": "Hypertension — First-Line Pharmacotherapy",
            "text": (
                "JNC guidelines recommend thiazide diuretics, ACE inhibitors, ARBs, or "
                "calcium channel blockers as first-line agents. ACE inhibitors are preferred "
                "in diabetic patients and those with CKD due to nephroprotective effects."
            ),
            "mesh_terms": ["Hypertension", "Antihypertensive Agents", "ACE Inhibitors"],
        },
    ]

    docs_path = os.path.join(output_dir, "docs.jsonl")
    with open(docs_path, "w") as f:
        for doc in sample_docs:
            f.write(json.dumps(doc) + "\n")

    logger.info("sample_kb_built", path=docs_path, doc_count=len(sample_docs))
