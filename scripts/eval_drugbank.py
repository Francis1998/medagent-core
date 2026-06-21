"""DrugBank drug interaction detection evaluation script.

Evaluates the DrugInteractionClient against a test set of known drug
interactions and computes Precision, Recall, and F1 score.

Usage:
    python scripts/eval_drugbank.py \
        --data-path data/drugbank_interactions_test.json \
        --output results/drugbank_eval.json

Test file format (JSON array):
    [
        {
            "drug_a": "warfarin",
            "drug_b": "aspirin",
            "has_interaction": true,
            "severity": "HIGH"
        },
        ...
    ]

If the test file is not found, the script runs in DEMO mode with a
small synthetic test set.
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

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from medagent.logging_config import configure_logging, get_logger
from medagent.models import Medication
from medagent.retrieval.drug_interaction import DrugInteractionClient

configure_logging("INFO")
logger = get_logger(__name__)


async def evaluate_pair(
    client: DrugInteractionClient,
    drug_a: str,
    drug_b: str,
    expected_interaction: bool,
) -> dict[str, Any]:
    """Evaluate a single drug pair against the expected interaction label.

    Args:
        client: Configured DrugInteractionClient.
        drug_a: First drug name.
        drug_b: Second drug name.
        expected_interaction: True if an interaction is expected.

    Returns:
        Dict with drug_a, drug_b, expected, predicted, correct, elapsed.
    """
    meds = [
        Medication(name=drug_a),
        Medication(name=drug_b),
    ]

    start = time.monotonic()
    try:
        warnings = await client.check_interactions(meds)
        predicted = len(warnings) > 0
    except Exception as exc:
        logger.warning("pair_eval_error", drug_a=drug_a, drug_b=drug_b, error=str(exc))
        predicted = False
    elapsed = time.monotonic() - start

    return {
        "drug_a": drug_a,
        "drug_b": drug_b,
        "expected": expected_interaction,
        "predicted": predicted,
        "correct": predicted == expected_interaction,
        "elapsed_seconds": round(elapsed, 3),
    }


def compute_metrics(results: list[dict[str, Any]]) -> dict[str, float]:
    """Compute Precision, Recall, and F1 from binary interaction predictions.

    Args:
        results: List of pair evaluation dicts.

    Returns:
        Dict with precision, recall, f1, accuracy.
    """
    tp = sum(1 for r in results if r["expected"] and r["predicted"])
    fp = sum(1 for r in results if not r["expected"] and r["predicted"])
    fn = sum(1 for r in results if r["expected"] and not r["predicted"])
    tn = sum(1 for r in results if not r["expected"] and not r["predicted"])

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / len(results) if results else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
    }


async def main(data_path: str, output_path: str) -> None:
    """Run DrugBank evaluation and persist results.

    Args:
        data_path: Path to the DrugBank test JSON file.
        output_path: Path to write JSON results.
    """
    data_path_resolved = Path(data_path)
    if not data_path_resolved.exists():
        logger.warning(
            "drugbank_data_not_found",
            path=str(data_path_resolved),
            message="Running in DEMO mode with synthetic test pairs",
        )
        test_pairs = _synthetic_test_pairs()
    else:
        with data_path_resolved.open() as f:
            test_pairs = json.load(f)

    logger.info("drugbank_eval_start", total_pairs=len(test_pairs))
    client = DrugInteractionClient()

    tasks = [
        evaluate_pair(
            client,
            pair["drug_a"],
            pair["drug_b"],
            pair.get("has_interaction", True),
        )
        for pair in test_pairs
    ]
    results = await asyncio.gather(*tasks)

    metrics = compute_metrics(list(results))
    output = {
        "total_pairs": len(results),
        "metrics": metrics,
        "results": list(results),
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'=' * 60}")
    print("DrugBank Interaction Detection Results")
    print(f"{'=' * 60}")
    print(f"Total pairs    : {len(results)}")
    print(f"Precision      : {metrics['precision']:.4f}")
    print(f"Recall         : {metrics['recall']:.4f}")
    print(f"F1 Score       : {metrics['f1']:.4f}")
    print(f"Accuracy       : {metrics['accuracy']:.4f}")
    print(f"Results saved  : {output_path}")
    print(f"{'=' * 60}\n")


def _synthetic_test_pairs() -> list[dict[str, Any]]:
    """Return a small synthetic test set for demo mode."""
    return [
        {"drug_a": "warfarin", "drug_b": "aspirin", "has_interaction": True},
        {"drug_a": "metformin", "drug_b": "contrast", "has_interaction": True},
        {"drug_a": "lisinopril", "drug_b": "potassium", "has_interaction": True},
        {"drug_a": "atorvastatin", "drug_b": "clarithromycin", "has_interaction": True},
        {"drug_a": "amoxicillin", "drug_b": "vitamin_c", "has_interaction": False},
        {"drug_a": "metoprolol", "drug_b": "calcium_carbonate", "has_interaction": False},
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run DrugBank interaction evaluation")
    parser.add_argument(
        "--data-path",
        default="./data/drugbank_interactions_test.json",
        help="Path to DrugBank test JSON file",
    )
    parser.add_argument(
        "--output",
        default="results/drugbank_eval.json",
        help="Output path for JSON results",
    )
    args = parser.parse_args()
    asyncio.run(main(args.data_path, args.output))
