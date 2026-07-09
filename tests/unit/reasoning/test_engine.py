"""Tests for the reasoning engine's LLM response parsing."""

from __future__ import annotations

from medagent.models import RetrievedDocument
from medagent.reasoning.engine import ReasoningEngine


def _doc() -> RetrievedDocument:
    """Build a minimal retrieved document for parsing tests.

    Returns:
        A RetrievedDocument used as an evidence source.
    """
    return RetrievedDocument(
        source="pubmed",
        doc_id="pmid-1",
        title="Evidence",
        snippet="snippet",
        relevance_score=0.7,
    )


_HYPOTHESIS_JSON = (
    '{"hypotheses": [{"label": "Community-acquired pneumonia", '
    '"icd_code": "J18.9", '
    '"evidence_for": [{"statement": "fever and productive cough", "strength": 0.7}], '
    '"evidence_against": [], "uncertainty_note": null}]}'
)


def test_parse_llm_response_handles_uppercase_json_fence() -> None:
    """An uppercase ```JSON code fence must not break hypothesis parsing.

    Some models wrap structured output in an uppercase ```JSON fence. The
    previous case-sensitive ``(?:json)?`` fence strip left the literal ``JSON``
    tag in the payload, so ``json.loads`` raised and every hypothesis was
    silently dropped. The language tag is now stripped case-insensitively.
    """
    engine = ReasoningEngine()
    response = f"```JSON\n{_HYPOTHESIS_JSON}\n```"

    hypotheses = engine._parse_llm_response(response, [_doc()])

    assert len(hypotheses) == 1
    assert hypotheses[0].label == "Community-acquired pneumonia"
    assert hypotheses[0].icd_code == "J18.9"
    assert len(hypotheses[0].evidence_for) == 1


def test_parse_llm_response_handles_lowercase_and_bare_fences() -> None:
    """Lowercase ```json and bare ``` fences continue to parse correctly."""
    engine = ReasoningEngine()

    lowercase = engine._parse_llm_response(f"```json\n{_HYPOTHESIS_JSON}\n```", [_doc()])
    bare = engine._parse_llm_response(f"```\n{_HYPOTHESIS_JSON}\n```", [_doc()])
    unfenced = engine._parse_llm_response(_HYPOTHESIS_JSON, [_doc()])

    assert len(lowercase) == 1
    assert len(bare) == 1
    assert len(unfenced) == 1


def test_parse_llm_response_accepts_string_evidence_items() -> None:
    """Evidence given as bare strings must not drop the whole hypothesis.

    The prompt asks for ``{"statement": ..., "strength": ...}`` objects, but
    models frequently emit each evidence item as a bare string. The previous
    ``e.get("statement")`` assumed a dict and raised ``AttributeError`` on a
    string, which was caught one level up and silently discarded the entire
    hypothesis. String evidence must be parsed into a statement with a neutral
    default strength instead.
    """
    engine = ReasoningEngine()
    response = (
        '{"hypotheses": [{"label": "Community-acquired pneumonia", '
        '"evidence_for": ["productive cough", "fever", "elevated WBC"], '
        '"evidence_against": ["no chest pain"], "uncertainty_note": null}]}'
    )

    hypotheses = engine._parse_llm_response(response, [_doc()])

    assert len(hypotheses) == 1
    hypothesis = hypotheses[0]
    assert hypothesis.label == "Community-acquired pneumonia"
    assert [item.statement for item in hypothesis.evidence_for] == [
        "productive cough",
        "fever",
        "elevated WBC",
    ]
    assert all(item.strength == 0.5 for item in hypothesis.evidence_for)
    assert [item.statement for item in hypothesis.evidence_against] == ["no chest pain"]


def test_parse_llm_response_clamps_out_of_range_strength() -> None:
    """An out-of-range numeric strength is clamped rather than dropping the item."""
    engine = ReasoningEngine()
    response = (
        '{"hypotheses": [{"label": "Sepsis", '
        '"evidence_for": [{"statement": "hypotension", "strength": 1.8}], '
        '"evidence_against": [], "uncertainty_note": null}]}'
    )

    hypotheses = engine._parse_llm_response(response, [_doc()])

    assert len(hypotheses) == 1
    assert hypotheses[0].evidence_for[0].strength == 1.0
