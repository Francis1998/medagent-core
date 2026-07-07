"""Tests for the PubMed E-utilities article parser."""

from __future__ import annotations

from medagent.retrieval.pubmed import _parse_article


def test_parse_article_handles_string_pmid() -> None:
    """A bare-string PMID must parse, not crash the article.

    NCBI JSON renders a single-valued element with no attributes as a bare
    string, so ``PMID`` can arrive as ``"40012345"`` rather than
    ``{"#text": "40012345"}``. The parser's fallback (``or medline["PMID"]``)
    shows this shape was intended to be supported, but ``.get("#text")`` was
    called on the string first, raising ``AttributeError`` — which the caller
    swallowed, silently dropping an otherwise valid article.
    """
    article = {
        "MedlineCitation": {
            "PMID": "40012345",
            "Article": {"ArticleTitle": "A Study of RAG"},
        }
    }

    doc = _parse_article(article)

    assert doc is not None
    assert doc.doc_id == "40012345"
    assert doc.title == "A Study of RAG"
    assert doc.url == "https://pubmed.ncbi.nlm.nih.gov/40012345/"


def test_parse_article_handles_dict_pmid() -> None:
    """A structured ``{"#text": ...}`` PMID continues to parse correctly."""
    article = {
        "MedlineCitation": {
            "PMID": {"@Version": "1", "#text": "40012345"},
            "Article": {"ArticleTitle": "A Study of RAG"},
        }
    }

    doc = _parse_article(article)

    assert doc is not None
    assert doc.doc_id == "40012345"


def test_parse_article_returns_none_without_pmid_or_title() -> None:
    """An article missing a PMID or a title yields no document."""
    assert _parse_article({"MedlineCitation": {"Article": {"ArticleTitle": "T"}}}) is None
    assert _parse_article({"MedlineCitation": {"PMID": "1"}}) is None
