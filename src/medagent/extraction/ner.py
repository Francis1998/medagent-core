"""Biomedical Named Entity Recognition using scispaCy.

Wraps a scispaCy pipeline (en_ner_bc5cdr_md by default) and normalises
entity labels to a canonical schema. Falls back to rule-based heuristics
when scispaCy is not installed, so the rest of the pipeline remains
testable without the full ML model stack.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from medagent.logging_config import get_logger
from medagent.models import ClinicalEntity

logger = get_logger(__name__)

# Canonical label map from scispaCy model labels → our schema
_LABEL_MAP: dict[str, str] = {
    "DISEASE": "DISEASE",
    "CHEMICAL": "CHEMICAL",
    "GENE_OR_GENE_PRODUCT": "GENE",
    "ORGANISM": "ORGANISM",
    "CELL_TYPE": "CELL_TYPE",
    "CELL_LINE": "CELL_LINE",
    "DNA": "DNA",
    "RNA": "RNA",
    "PROTEIN": "PROTEIN",
    # BC5CDR labels
    "Disease": "DISEASE",
    "Chemical": "CHEMICAL",
}

# Fallback patterns used when scispaCy is unavailable
_FALLBACK_PATTERNS: list[tuple[str, str]] = [
    (
        r"\b(diabetes|hypertension|myocardial infarction|pneumonia|sepsis|"
        r"heart failure|stroke|asthma|COPD|depression|anxiety|cancer|tumor|"
        r"fibrosis|cirrhosis|arrhythmia|bradycardia|tachycardia|hypoxia)\b",
        "DISEASE",
    ),
    (
        r"\b(metformin|lisinopril|atorvastatin|aspirin|warfarin|heparin|"
        r"amoxicillin|penicillin|ibuprofen|acetaminophen|insulin|prednisone|"
        r"furosemide|metoprolol|amlodipine|losartan|omeprazole|simvastatin)\b",
        "CHEMICAL",
    ),
    (
        r"\b(troponin|creatinine|HbA1c|hemoglobin|WBC|platelet|albumin|"
        r"sodium|potassium|glucose|BNP|INR|TSH|LDL|HDL)\b",
        "GENE",
    ),
]


class EntityExtractor:
    """Biomedical entity extractor backed by scispaCy or rule-based fallback.

    Args:
        model_name: scispaCy model identifier. Defaults to ``en_ner_bc5cdr_md``.
        use_fallback: When True, skip loading spaCy and use regex patterns.
            Useful for testing without the full model installed.
        timeout_seconds: Hard timeout for a single extract() call.
    """

    def __init__(
        self,
        model_name: str = "en_ner_bc5cdr_md",
        use_fallback: bool = False,
        timeout_seconds: int = 10,
    ) -> None:
        self._model_name = model_name
        self._timeout = timeout_seconds
        self._nlp: Any = None

        if not use_fallback:
            self._nlp = self._load_spacy_model(model_name)

    @staticmethod
    def _load_spacy_model(model_name: str) -> Any:
        """Attempt to load a scispaCy model; log and return None on failure."""
        try:
            import spacy  # type: ignore[import-untyped]

            nlp = spacy.load(model_name)
            logger.info("spacy_model_loaded", model=model_name)
            return nlp
        except Exception as exc:
            logger.warning(
                "spacy_model_unavailable",
                model=model_name,
                error=str(exc),
                fallback="regex",
            )
            return None

    async def extract(self, text: str) -> list[ClinicalEntity]:
        """Extract biomedical entities from clinical text.

        Runs spaCy synchronously in a thread pool to avoid blocking the
        async event loop during model inference.

        Args:
            text: Combined clinical notes and chief complaint.

        Returns:
            Deduplicated list of ClinicalEntity objects sorted by start_char.

        Raises:
            asyncio.TimeoutError: If extraction exceeds timeout_seconds.
        """
        if not text.strip():
            return []

        try:
            return await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, self._extract_sync, text),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "entity_extraction_timeout",
                timeout_seconds=self._timeout,
                text_length=len(text),
            )
            return self._fallback_extract(text)

    def _extract_sync(self, text: str) -> list[ClinicalEntity]:
        """Synchronous extraction — called from thread pool."""
        if self._nlp is not None:
            return self._spacy_extract(text)
        return self._fallback_extract(text)

    def _spacy_extract(self, text: str) -> list[ClinicalEntity]:
        """Run scispaCy NER and convert ents to ClinicalEntity objects."""
        doc = self._nlp(text)
        seen: set[str] = set()
        entities: list[ClinicalEntity] = []

        for ent in doc.ents:
            key = f"{ent.text.lower()}|{ent.label_}"
            if key in seen:
                continue
            seen.add(key)
            label = _LABEL_MAP.get(ent.label_, ent.label_)
            entities.append(
                ClinicalEntity(
                    text=ent.text,
                    label=label,
                    start_char=ent.start_char,
                    end_char=ent.end_char,
                )
            )

        return sorted(entities, key=lambda e: e.start_char or 0)

    def _fallback_extract(self, text: str) -> list[ClinicalEntity]:
        """Regex-based entity extraction used when scispaCy is unavailable."""
        seen: set[str] = set()
        entities: list[ClinicalEntity] = []

        for pattern, label in _FALLBACK_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                term = match.group(0)
                key = f"{term.lower()}|{label}"
                if key in seen:
                    continue
                seen.add(key)
                entities.append(
                    ClinicalEntity(
                        text=term,
                        label=label,
                        start_char=match.start(),
                        end_char=match.end(),
                    )
                )

        return sorted(entities, key=lambda e: e.start_char or 0)

    def get_mesh_terms(self, entities: list[ClinicalEntity]) -> list[str]:
        """Extract candidate MeSH terms from entity texts.

        Converts entity text to title-case as a simple MeSH approximation.
        A production system would look these up against the UMLS Metathesaurus.

        Args:
            entities: List of extracted clinical entities.

        Returns:
            List of MeSH-candidate strings.
        """
        return list(
            {e.text.title() for e in entities if e.label in {"DISEASE", "CHEMICAL", "GENE"}}
        )
