"""Local knowledge base ingestion script.

Ingests biomedical documents into the local KB index used for hybrid
BM25 + dense retrieval. Accepts JSONL files where each line is a document:

    {"id": "...", "title": "...", "text": "...", "mesh_terms": [...]}

Usage:
    # Build the sample KB (no data required):
    python scripts/ingest_kb.py --sample

    # Ingest a custom JSONL file:
    python scripts/ingest_kb.py \
        --input data/custom_corpus.jsonl \
        --output data/kb_index/

    # Ingest PubMed abstracts directly (requires PUBMED_API_KEY in .env):
    python scripts/ingest_kb.py \
        --pubmed-terms "myocardial infarction" "drug interaction" \
        --output data/kb_index/
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from medagent.logging_config import configure_logging, get_logger
from medagent.retrieval.local_kb import build_sample_index
from medagent.retrieval.pubmed import PubMedClient

configure_logging("INFO")
logger = get_logger(__name__)


def ingest_from_jsonl(input_path: str, output_dir: str) -> int:
    """Ingest documents from a JSONL file into the KB index directory.

    Args:
        input_path: Path to the source JSONL file.
        output_dir: Directory to write the index into.

    Returns:
        Number of documents ingested.
    """
    input_resolved = Path(input_path)
    if not input_resolved.exists():
        logger.error("input_file_not_found", path=str(input_resolved))
        return 0

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "docs.jsonl")

    count = 0
    with input_resolved.open() as fin, open(output_path, "a") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                doc: dict[str, Any] = json.loads(line)
                if "title" in doc and "text" in doc:
                    fout.write(json.dumps(doc) + "\n")
                    count += 1
            except json.JSONDecodeError as exc:
                logger.warning("jsonl_parse_error", error=str(exc))

    logger.info("ingest_complete", count=count, output=output_path)
    return count


async def ingest_from_pubmed(
    terms: list[str],
    output_dir: str,
    max_per_term: int = 10,
) -> int:
    """Fetch PubMed abstracts for each MeSH term and ingest into the KB.

    Args:
        terms: List of MeSH terms to query.
        output_dir: Directory to write the index into.
        max_per_term: Maximum documents to fetch per term.

    Returns:
        Total number of documents ingested.
    """
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "docs.jsonl")

    client = PubMedClient(max_results=max_per_term)
    total = 0

    with open(output_path, "a") as fout:
        for term in terms:
            logger.info("fetching_pubmed", term=term)
            try:
                docs = await client.search([term])
                for doc in docs:
                    row = {
                        "id": doc.doc_id,
                        "title": doc.title,
                        "text": doc.snippet,
                        "url": doc.url,
                        "mesh_terms": doc.mesh_terms,
                        "published_date": doc.published_date,
                        "source": "pubmed",
                    }
                    fout.write(json.dumps(row) + "\n")
                    total += 1
                logger.info("pubmed_term_done", term=term, count=len(docs))
            except Exception as exc:
                logger.warning("pubmed_term_error", term=term, error=str(exc))

    logger.info("pubmed_ingest_complete", total=total, output=output_path)
    return total


async def main() -> None:
    """Entry point for the ingest script."""
    parser = argparse.ArgumentParser(description="Ingest documents into the local KB index")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Build the built-in sample index (no data required)",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Path to a JSONL document file to ingest",
    )
    parser.add_argument(
        "--pubmed-terms",
        nargs="+",
        default=None,
        help="MeSH terms to fetch from PubMed",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./data/kb_index/",
        help="Output directory for the KB index",
    )
    parser.add_argument(
        "--max-per-term",
        type=int,
        default=10,
        help="Maximum PubMed documents per term",
    )
    args = parser.parse_args()

    if args.sample:
        build_sample_index(output_dir=args.output)
        print(f"Sample KB index built at {args.output}")
        return

    if args.input:
        count = ingest_from_jsonl(args.input, args.output)
        print(f"Ingested {count} documents from {args.input}")

    if args.pubmed_terms:
        count = await ingest_from_pubmed(
            args.pubmed_terms, args.output, args.max_per_term
        )
        print(f"Ingested {count} documents from PubMed")

    if not args.input and not args.pubmed_terms and not args.sample:
        print("No action specified. Use --sample, --input, or --pubmed-terms.")
        print("Run with --help for usage information.")


if __name__ == "__main__":
    asyncio.run(main())
