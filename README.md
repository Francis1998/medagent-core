# medagent-core

> **⚠️ RESEARCH USE ONLY — NOT FDA-cleared — NOT for clinical deployment**

**Auditable biomedical AI decision support agent** — multi-hop clinical reasoning, drug interaction detection, and safety-first agentic architecture for health-AI research.

[![CI](https://github.com/Francis1998/medagent-core/actions/workflows/ci.yml/badge.svg)](https://github.com/Francis1998/medagent-core/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)
[![Research Use Only](https://img.shields.io/badge/Use-Research%20Only-red.svg)](#safety)

---

## What Is This?

`medagent-core` is a production-structured, open-source reference implementation of a **safety-first clinical AI reasoning agent**. It is built for researchers and health-AI engineers exploring:

- **Agentic AI in high-stakes domains** — explicit state machines, not black-box LLM wrappers
- **Multi-hop biomedical reasoning** — evidence retrieval + Bayesian hypothesis ranking
- **LLM routing and fallback** — task-specific provider selection with automatic failover
- **Clinical AI safety patterns** — PII de-identification, scope enforcement, escalation triggers, mandatory disclaimers

Inspired by [AgenticHealthAI](https://arxiv.org/search/?searchtype=all&query=AgenticHealthAI), [LangGraph](https://github.com/langchain-ai/langgraph), and OpenClaw medical skills patterns.

---

## Architecture Overview

```
INTAKE → ENTITY_EXTRACTION → KNOWLEDGE_RETRIEVAL → REASONING → SAFETY_CHECK → OUTPUT
                                                                         ↓
                                                                      ESCALATE
```

The agent implements a strict **Observe → Decide → Act** loop as a finite state machine:

| Stage | Component | Description |
|---|---|---|
| **Observe** | `extraction/` | scispaCy NER + FHIR R4 parser → clinical entities |
| **Decide** | `reasoning/` | Bayesian hypothesis ranking with LLM evidence chains |
| **Act** | `agent/` | State machine → OUTPUT or ESCALATE; durable audit log |

### Key Components

- **`src/medagent/agent/`** — State machine, planner, escalation logic, SQLAlchemy audit log
- **`src/medagent/extraction/`** — scispaCy NER (with regex fallback), FHIR R4 bundle parser, PII boundary
- **`src/medagent/retrieval/`** — PubMed (ESearch/EFetch), OpenFDA + RxNorm drug interactions, local KB (BM25 + dense hybrid)
- **`src/medagent/reasoning/`** — Bayesian scorer, evidence chain builder, confidence calibrator
- **`src/medagent/llm/`** — BaseLLMAdapter + OpenAI / Anthropic / Google / Kimi adapters, medical router, output validator
- **`src/medagent/safety/`** — Mandatory disclaimers, HMAC-SHA256 PII hashing, scope enforcer, jailbreak detection
- **`src/medagent/api/`** — FastAPI: `/analyze`, `/drug-interactions`, `/health`

---

## Safety

This system includes multiple layers of safety controls. See **[SAFETY.md](SAFETY.md)** for the full policy.

**Hard constraints enforced in code:**
- Every output includes a mandatory `disclaimer` field injected at model construction time
- Every LLM call uses a system prompt prohibiting direct prescriptions and code execution
- Drug interaction warnings require ≥2 independent sources (enforced by Pydantic validator)
- Confidence < 0.6 → automatic `ESCALATE` state (human review required)
- PII fields hashed before any LLM call
- 120-second total hard timeout

---

## Quick Start

```bash
git clone https://github.com/Francis1998/medagent-core.git
cd medagent-core
pip install -e ".[dev]"
cp .env.example .env   # Add at least one LLM API key
python scripts/ingest_kb.py --sample
uvicorn medagent.api.main:app --reload
```

See [QUICKSTART.md](QUICKSTART.md) for the full guide including Docker Compose setup.

---

## API

### POST `/analyze`

Full clinical reasoning run. Accepts a FHIR-compatible patient context and a free-text query.

```json
{
  "patient_context": {
    "patient_id_hash": "<sha256 of patient MRN>",
    "age": 65,
    "sex": "male",
    "chief_complaint": "Chest pain radiating to left arm",
    "clinical_notes": "2-hour history of crushing chest pain...",
    "medications": [{"name": "aspirin"}],
    "lab_results": [{"test_name": "Troponin I", "value": "2.4", "unit": "ng/mL", "abnormal": true}]
  },
  "query": "What is the differential diagnosis?"
}
```

**Response** includes:
- `ranked_hypotheses` — differential with Bayesian scores and evidence chains
- `drug_interactions_flagged` — dual-source validated interaction warnings
- `overall_confidence` — calibrated confidence score
- `escalated` — true if human review is required
- `evidence_chain` — retrieved documents supporting the reasoning
- `disclaimer` — mandatory safety disclaimer (always present)

### POST `/drug-interactions`

Targeted drug interaction check for a medication list.

### GET `/health`

Readiness probe.

---

## Benchmarks

| Script | Metric | Description |
|---|---|---|
| `scripts/eval_medqa.py` | Accuracy | USMLE-style 4-option MCQ |
| `scripts/eval_drugbank.py` | F1 / Precision / Recall | Drug interaction detection |

```bash
python scripts/eval_medqa.py --max-samples 100
python scripts/eval_drugbank.py
```

Results saved to `results/`.

---

## Quality Gates

All PRs must pass:

```bash
ruff check src/         # zero errors
ruff format --check src/ # zero format violations
mypy src/               # zero type errors
pytest tests/ -v        # all pass
```

---

## Repository Structure

```
medagent-core/
├── src/medagent/       # Main package
│   ├── agent/          # State machine + audit log
│   ├── extraction/     # NER + FHIR parser
│   ├── retrieval/      # PubMed + DrugBank + local KB
│   ├── reasoning/      # Bayesian scoring + LLM engine
│   ├── llm/            # Adapters + router + validator
│   ├── safety/         # Disclaimers + PII + scope
│   └── api/            # FastAPI endpoints
├── tests/              # pytest test suite
├── scripts/            # eval_medqa.py, eval_drugbank.py, ingest_kb.py
├── data/               # Sample FHIR JSON, KB index
├── results/            # Benchmark outputs
├── .github/workflows/  # CI: ruff, mypy, pytest, Docker
├── docker-compose.yml
├── Dockerfile
├── QUICKSTART.md
├── CONFIGURATION.md
├── SAFETY.md
└── ARCHITECTURE.md
```

---

## Research Context

This project directly extends published research on:
- AI-assisted drug discovery and biomedical reasoning reliability
- Safety-first agentic AI design patterns
- Hybrid retrieval (dense + sparse + rerank) for biomedical literature
- Confidence calibration in LLM-based clinical reasoning

If you use this work in research, please cite this repository.

---

## Contributing

Contributions welcome. Please:
1. Open an issue before large PRs
2. Tag safety-relevant issues with `safety-critical`
3. Ensure `ruff`, `mypy`, and `pytest` pass before submitting

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

## Disclaimer

**This software is provided for research and educational purposes only. It is NOT intended for clinical use, medical diagnosis, or treatment planning. It has NOT been evaluated, validated, or cleared by any regulatory authority including the U.S. FDA or EMA. Do NOT use this system to make clinical decisions. Always consult a qualified healthcare professional.**
