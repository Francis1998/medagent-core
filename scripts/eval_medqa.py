"""MedQA (USMLE-style) benchmark evaluation script.

Runs the medagent reasoning engine on a subset of MedQA 4-option
multiple-choice questions and reports accuracy.

Usage:
    python scripts/eval_medqa.py \
        --data-path data/medqa_usmle_4_options_test.jsonl \
        --max-samples 100 \
        --output results/medqa_eval.json

Each question is sent to the reasoning engine. The engine's top hypothesis
is matched against the correct answer using substring matching.

NOTE: This script requires valid LLM API keys configured in .env.
      Without keys the engine falls back to heuristic-only reasoning.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# Ensure the src directory is on the path when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from medagent.config import settings
from medagent.extraction.ner import EntityExtractor
from medagent.llm.router import MedicalRouter
from medagent.logging_config import configure_logging, get_logger
from medagent.models import ClinicalQuery, FHIRPatientContext
from medagent.reasoning.engine import ReasoningEngine
from medagent.retrieval.local_kb import LocalKnowledgeBase, build_sample_index
from medagent.retrieval.orchestrator import RetrievalOrchestrator
from medagent.safety.pii_hasher import hash_pii

configure_logging("INFO")
logger = get_logger(__name__)


async def run_single_question(
    question: dict[str, Any],
    reasoner: ReasoningEngine,
    extractor: EntityExtractor,
    retriever: RetrievalOrchestrator,
    router: MedicalRouter,
) -> dict[str, Any]:
    """Run the agent on a single MedQA question and return the result dict.

    Args:
        question: MedQA question dict with keys: question, options, answer.
        reasoner: Configured reasoning engine.
        extractor: NER entity extractor.
        retriever: Retrieval orchestrator.
        router: Multi-LLM medical router.

    Returns:
        Dict with question_id, correct_answer, top_hypothesis, correct (bool), elapsed.
    """
    question_text: str = question.get("question", "")
    options: dict[str, str] = question.get("options", {})
    correct_answer_key: str = question.get("answer", "")
    correct_answer_text: str = options.get(correct_answer_key, "")

    # Format as a clinical query
    options_str = "\n".join(f"{k}: {v}" for k, v in options.items())
    query_text = (
        f"USMLE Question:\n{question_text}\n\nOptions:\n{options_str}\n\n"
        "Identify the most likely correct answer from the options above based on "
        "your clinical reasoning."
    )

    patient_id_hash = hash_pii(f"medqa-{question.get('id', 'unknown')}")
    ctx = FHIRPatientContext(
        patient_id_hash=patient_id_hash,
        chief_complaint=question_text[:200],
        clinical_notes=question_text,
    )
    query = ClinicalQuery(patient_context=ctx, query=query_text)

    start = time.monotonic()
    entities = await extractor.extract(question_text)
    docs, _ = await retriever.retrieve(entities=entities, medications=[])
    hypotheses = await reasoner.reason(
        query=query,
        entities=entities,
        docs=docs,
        router=router,
    )
    elapsed = time.monotonic() - start

    top_hypothesis = hypotheses[0].label if hypotheses else "No hypothesis"

    # Check correctness: does the top hypothesis contain the correct answer text?
    correct = (
        correct_answer_text.lower() in top_hypothesis.lower()
        or top_hypothesis.lower() in correct_answer_text.lower()
    )

    return {
        "question_id": question.get("id", "unknown"),
        "question_preview": question_text[:100],
        "correct_answer": correct_answer_text,
        "top_hypothesis": top_hypothesis,
        "correct": correct,
        "elapsed_seconds": round(elapsed, 3),
    }


async def main(
    data_path: str,
    max_samples: int,
    output_path: str,
) -> None:
    """Run MedQA evaluation and persist results.

    Args:
        data_path: Path to MedQA JSONL file.
        max_samples: Maximum number of questions to evaluate.
        output_path: Path to write JSON results.
    """
    data_path_resolved = Path(data_path)
    if not data_path_resolved.exists():
        logger.warning(
            "medqa_data_not_found",
            path=str(data_path_resolved),
            message="Running in DEMO mode with 3 synthetic questions",
        )
        questions = _synthetic_questions()
    else:
        questions = []
        with data_path_resolved.open() as f:
            for line in f:
                if len(questions) >= max_samples:
                    break
                line = line.strip()
                if line:
                    try:
                        questions.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    logger.info("medqa_eval_start", total_questions=len(questions))

    # Build sample KB for retrieval
    build_sample_index()

    extractor = EntityExtractor(use_fallback=True)
    retriever = RetrievalOrchestrator(local_kb=LocalKnowledgeBase())
    reasoner = ReasoningEngine(timeout_seconds=settings.agent_reasoning_timeout)
    router = MedicalRouter.from_settings()

    results: list[dict[str, Any]] = []
    correct_count = 0

    for i, question in enumerate(questions):
        try:
            result = await run_single_question(
                question, reasoner, extractor, retriever, router
            )
            results.append(result)
            if result["correct"]:
                correct_count += 1
            logger.info(
                "medqa_question_done",
                idx=i + 1,
                total=len(questions),
                correct=result["correct"],
                elapsed=result["elapsed_seconds"],
            )
        except Exception as exc:
            logger.warning("medqa_question_error", idx=i, error=str(exc))
            results.append({"question_id": question.get("id", i), "error": str(exc)})

    accuracy = correct_count / len(results) if results else 0.0
    summary = {
        "total_questions": len(results),
        "correct": correct_count,
        "accuracy": round(accuracy, 4),
        "results": results,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'='*60}")
    print("MedQA Evaluation Results")
    print(f"{'='*60}")
    print(f"Total questions : {len(results)}")
    print(f"Correct         : {correct_count}")
    print(f"Accuracy        : {accuracy:.1%}")
    print(f"Results saved to: {output_path}")
    print(f"{'='*60}\n")


def _synthetic_questions() -> list[dict[str, Any]]:
    """Return 3 synthetic USMLE-style questions for demo mode."""
    return [
        {
            "id": "demo-001",
            "question": (
                "A 65-year-old man presents with sudden onset chest pain radiating to the "
                "left arm, diaphoresis, and shortness of breath. ECG shows ST elevation "
                "in leads II, III, and aVF. What is the most likely diagnosis?"
            ),
            "options": {
                "A": "Myocardial Infarction",
                "B": "Pulmonary Embolism",
                "C": "Aortic Dissection",
                "D": "Pericarditis",
            },
            "answer": "A",
        },
        {
            "id": "demo-002",
            "question": (
                "A 45-year-old woman with Type 2 diabetes presents with HbA1c of 9.2%, "
                "polyuria, and polydipsia. She is currently on metformin 1000mg BID. "
                "Which additional medication class is most appropriate to consider?"
            ),
            "options": {
                "A": "GLP-1 receptor agonist",
                "B": "Statin",
                "C": "ACE inhibitor",
                "D": "Beta-blocker",
            },
            "answer": "A",
        },
        {
            "id": "demo-003",
            "question": (
                "A 30-year-old woman presents with fatigue, pallor, and shortness of breath "
                "on exertion. Lab results show hemoglobin 8.2 g/dL, MCV 70 fL, and low "
                "serum ferritin. What is the most likely diagnosis?"
            ),
            "options": {
                "A": "Iron Deficiency Anemia",
                "B": "Vitamin B12 Deficiency",
                "C": "Hemolytic Anemia",
                "D": "Aplastic Anemia",
            },
            "answer": "A",
        },
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run MedQA benchmark evaluation")
    parser.add_argument(
        "--data-path",
        default=settings.medqa_data_path,
        help="Path to MedQA USMLE JSONL file",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=settings.eval_max_samples,
        help="Maximum number of questions to evaluate",
    )
    parser.add_argument(
        "--output",
        default="results/medqa_eval.json",
        help="Output path for JSON results",
    )
    args = parser.parse_args()
    asyncio.run(main(args.data_path, args.max_samples, args.output))
