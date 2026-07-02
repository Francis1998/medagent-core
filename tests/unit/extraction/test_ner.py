"""Tests for the EntityExtractor (fallback/regex mode)."""

from __future__ import annotations

import pytest

from medagent.extraction.ner import EntityExtractor


@pytest.fixture()
def extractor() -> EntityExtractor:
    """Return an EntityExtractor in fallback (regex) mode for fast tests."""
    return EntityExtractor(use_fallback=True)


class TestEntityExtractor:
    """Tests for regex-based entity extraction."""

    @pytest.mark.asyncio()
    async def test_extract_disease_entity(self, extractor: EntityExtractor) -> None:
        """Diabetes must be extracted as a DISEASE entity."""
        entities = await extractor.extract("Patient presents with diabetes and hypertension")
        labels = {e.label for e in entities}
        texts = {e.text.lower() for e in entities}
        assert "DISEASE" in labels
        assert "diabetes" in texts

    @pytest.mark.asyncio()
    async def test_extract_chemical_entity(self, extractor: EntityExtractor) -> None:
        """Metformin must be extracted as a CHEMICAL entity."""
        entities = await extractor.extract("Currently taking metformin 500mg daily")
        labels = {e.label for e in entities}
        texts = {e.text.lower() for e in entities}
        assert "CHEMICAL" in labels
        assert "metformin" in texts

    @pytest.mark.asyncio()
    async def test_empty_text_returns_empty(self, extractor: EntityExtractor) -> None:
        """Empty text must return an empty entity list."""
        entities = await extractor.extract("")
        assert entities == []

    @pytest.mark.asyncio()
    async def test_whitespace_text_returns_empty(self, extractor: EntityExtractor) -> None:
        """Whitespace-only text must return an empty entity list."""
        entities = await extractor.extract("   \n\t  ")
        assert entities == []

    @pytest.mark.asyncio()
    async def test_no_duplicates(self, extractor: EntityExtractor) -> None:
        """The same term repeated multiple times must appear only once."""
        entities = await extractor.extract("diabetes diabetes diabetes")
        texts = [e.text.lower() for e in entities]
        assert texts.count("diabetes") == 1

    @pytest.mark.asyncio()
    async def test_entities_sorted_by_char_position(self, extractor: EntityExtractor) -> None:
        """Entities must be sorted by start_char ascending."""
        entities = await extractor.extract("hypertension and diabetes with metformin treatment")
        positions = [e.start_char for e in entities if e.start_char is not None]
        assert positions == sorted(positions)

    def test_get_mesh_terms_filters_by_label(self, extractor: EntityExtractor) -> None:
        """get_mesh_terms must only return DISEASE, CHEMICAL, and GENE entities."""
        from medagent.models import ClinicalEntity

        entities = [
            ClinicalEntity(text="diabetes", label="DISEASE"),
            ClinicalEntity(text="metformin", label="CHEMICAL"),
            ClinicalEntity(text="unknown_label", label="ORGANISM"),
        ]
        mesh_terms = extractor.get_mesh_terms(entities)
        assert "Diabetes" in mesh_terms
        assert "Metformin" in mesh_terms
        assert "Unknown_Label" not in mesh_terms

    def test_get_mesh_terms_is_order_preserving_and_deduplicated(
        self, extractor: EntityExtractor
    ) -> None:
        """MeSH terms must follow entity order and de-duplicate deterministically.

        The previous set-comprehension implementation returned terms in a
        process-dependent (hash-randomised) order. Downstream, the retrieval
        orchestrator slices ``mesh_terms[:5]``, so a non-deterministic order
        silently selected a different subset of terms per run. The output must
        equal the first-seen order of qualifying entities.
        """
        from medagent.models import ClinicalEntity

        entities = [
            ClinicalEntity(text="diabetes", label="DISEASE"),
            ClinicalEntity(text="metformin", label="CHEMICAL"),
            ClinicalEntity(text="diabetes", label="DISEASE"),
            ClinicalEntity(text="troponin", label="GENE"),
            ClinicalEntity(text="aspirin", label="CHEMICAL"),
            ClinicalEntity(text="sepsis", label="DISEASE"),
        ]

        mesh_terms = extractor.get_mesh_terms(entities)

        assert mesh_terms == ["Diabetes", "Metformin", "Troponin", "Aspirin", "Sepsis"]


class TestEntityExtractorFallback:
    """Tests that validate fallback mode behavioural edge cases."""

    @pytest.mark.asyncio()
    async def test_mixed_case_extraction(self) -> None:
        """Extraction must be case-insensitive."""
        extractor = EntityExtractor(use_fallback=True)
        entities = await extractor.extract("Patient has DIABETES and takes WARFARIN")
        texts_lower = {e.text.lower() for e in entities}
        assert "diabetes" in texts_lower
        assert "warfarin" in texts_lower
