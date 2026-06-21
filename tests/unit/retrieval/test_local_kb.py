"""Tests for the LocalKnowledgeBase hybrid retrieval."""

from __future__ import annotations

import json
import os
import tempfile
from typing import TYPE_CHECKING

import pytest

from medagent.models import ClinicalEntity
from medagent.retrieval.local_kb import LocalKnowledgeBase, build_sample_index

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.fixtures import FixtureRequest
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture


@pytest.fixture()
def sample_index_dir() -> str:
    """Create a temporary directory with a small sample index."""
    with tempfile.TemporaryDirectory() as tmpdir:
        build_sample_index(output_dir=tmpdir)
        yield tmpdir


class TestLocalKnowledgeBase:
    """Tests for LocalKnowledgeBase search behaviour."""

    def test_load_sample_index(self, sample_index_dir: str) -> None:
        """LocalKnowledgeBase must load the sample docs.jsonl without error."""
        kb = LocalKnowledgeBase(index_path=sample_index_dir, top_k=3)
        kb.load()
        assert len(kb._docs) > 0

    def test_search_returns_results(self, sample_index_dir: str) -> None:
        """A relevant query must return at least one document."""
        kb = LocalKnowledgeBase(index_path=sample_index_dir, top_k=3)
        kb.load()
        entities = [ClinicalEntity(text="diabetes", label="DISEASE")]
        results = kb.search(entities)
        assert len(results) > 0

    def test_search_results_are_retrieved_documents(self, sample_index_dir: str) -> None:
        """Search results must be RetrievedDocument instances."""
        from medagent.models import RetrievedDocument

        kb = LocalKnowledgeBase(index_path=sample_index_dir, top_k=3)
        kb.load()
        entities = [ClinicalEntity(text="metformin", label="CHEMICAL")]
        results = kb.search(entities)
        for doc in results:
            assert isinstance(doc, RetrievedDocument)

    def test_search_scores_in_unit_interval(self, sample_index_dir: str) -> None:
        """Relevance scores must be in [0, 1]."""
        kb = LocalKnowledgeBase(index_path=sample_index_dir, top_k=5)
        kb.load()
        entities = [ClinicalEntity(text="hypertension", label="DISEASE")]
        results = kb.search(entities)
        for doc in results:
            assert 0.0 <= doc.relevance_score <= 1.0

    def test_empty_entities_returns_empty(self, sample_index_dir: str) -> None:
        """An empty entity list must return no results."""
        kb = LocalKnowledgeBase(index_path=sample_index_dir, top_k=3)
        kb.load()
        results = kb.search([], query_text="")
        assert results == []

    def test_missing_index_path_returns_empty(self) -> None:
        """A non-existent index path must return empty results without raising."""
        kb = LocalKnowledgeBase(index_path="/nonexistent/path/", top_k=3)
        entities = [ClinicalEntity(text="diabetes", label="DISEASE")]
        results = kb.search(entities)
        assert results == []


class TestBuildSampleIndex:
    """Tests for the sample index builder utility."""

    def test_creates_docs_jsonl(self) -> None:
        """build_sample_index must create a docs.jsonl file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            build_sample_index(output_dir=tmpdir)
            docs_path = os.path.join(tmpdir, "docs.jsonl")
            assert os.path.exists(docs_path)

    def test_docs_are_valid_json(self) -> None:
        """Every line in docs.jsonl must be valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            build_sample_index(output_dir=tmpdir)
            docs_path = os.path.join(tmpdir, "docs.jsonl")
            with open(docs_path) as f:
                for line in f:
                    doc = json.loads(line)
                    assert "title" in doc
                    assert "text" in doc
