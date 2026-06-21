# medagent-core

> **⚠️ RESEARCH USE ONLY — NOT FDA-cleared — NOT for clinical deployment**

**Auditable biomedical AI decision support agent** — multi-hop clinical reasoning, drug interaction detection, and safety-first agentic architecture for health-AI research.

[![CI](https://github.com/Francis1998/medagent-core/actions/workflows/ci.yml/badge.svg)](https://github.com/Francis1998/medagent-core/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-93%20passing-brightgreen)](#quality-gates)
[![Research Use Only](https://img.shields.io/badge/Use-Research%20Only-red.svg)](SAFETY.md)

---

## Live Demo

### Full clinical reasoning pipeline (STEMI case)
![medagent pipeline demo](assets/demo_pipeline.svg)

### Drug interaction detection (polypharmacy)
![medagent drug interaction demo](assets/demo_drugcheck.svg)

### Automatic ESCALATE trigger (ambiguous presentation)
![medagent escalation demo](assets/demo_escalation.svg)

Run it yourself — no API keys needed:
```bash
git clone https://github.com/Francis1998/medagent-core && cd medagent-core
pip install -e ".[dev]" && python scripts/demo.py --case all
```

---

## The Problem

Clinical AI is broken in a predictable way.

**Most LLM wrappers used in health-AI today:**
- Feed patient data into a chat model and return raw text — no audit trail
- Cannot explain *why* they reached a conclusion (no evidence chain)
- Surface drug interaction warnings without cross-validation across sources
- Have no confidence calibration — they never say "I don't know"
- Cannot escalate to human review when uncertainty is high
- Log PII to LLM APIs in plain text
- Wrap `generate()` in a `try/except` and call it a "pipeline"

**The result:** researchers and health-AI engineers spend months re-inventing the same safety plumbing before they can test a single hypothesis. And every new team makes the same mistakes.

`medagent-core` is the reference implementation that solves these problems, openly and reproducibly, so teams can focus on the clinical problems instead.

---

## Who This Is For — and Real Use Cases

### 1. Emergency Department Triage Research
**Problem:** ED physicians see 150+ patients per shift. High-acuity presentations (chest pain, altered mental status, sepsis) require fast differential generation but cognitive load causes anchoring errors.

**How medagent-core helps:**
- Ingests triage FHIR data (vitals, chief complaint, prior diagnoses, meds) in under 2 seconds
- Runs NER to extract symptoms, medications, and lab values simultaneously
- Queries PubMed for the top relevant papers on each candidate diagnosis
- Returns a ranked differential with evidence FOR and AGAINST each hypothesis
- If confidence < 0.6 → automatically flags for senior physician review

**Research angle:** Study whether AI-assisted triage improves time-to-diagnosis or reduces cognitive anchoring in retrospective ED datasets.

```
Input:  65M, chest pain radiating to left arm, troponin-I 2.4 ng/mL, ST elevation II/III/aVF
Output: #1 STEMI (score 0.89) · #2 NSTEMI (0.61) · #3 Aortic Dissection (0.34)
        Drug interaction: aspirin + metoprolol → MODERATE bradycardia risk [2 sources]
        Recommended: immediate cardiology consult · primary PCI evaluation
```

---

### 2. Polypharmacy Safety — Automatic Interaction Screening
**Problem:** The average 65+ patient takes 5+ medications. Drug-drug interactions cause ~125,000 deaths per year in the US. Manual review is impractical at scale; existing tools surface too many false positives.

**How medagent-core helps:**
- Queries **both** RxNorm Interaction API **and** OpenFDA drug labels simultaneously
- Only surfaces a warning when **both** sources confirm the interaction (dual-source validation)
- Classifies by severity: CRITICAL / HIGH / MODERATE / LOW
- Provides mechanism and clinical consequence, not just a flag
- All warnings include source attribution for pharmacist verification

```python
# Real use case: warfarin + amiodarone co-prescription
POST /drug-interactions
{ "medications": ["warfarin 5mg", "amiodarone 200mg", "aspirin 81mg", "omeprazole 20mg"] }

→ CRITICAL: warfarin + amiodarone — CYP2C9 inhibition → 3-5× INR elevation
            validated ✓ (rxnorm + openfda)
→ MODERATE: warfarin + aspirin — additive anticoagulation + GI mucosal damage
→ MODERATE: omeprazole + warfarin — CYP2C19 inhibition, modest INR increase
```

**Research angle:** Measure false positive/negative rates vs DrugBank ground truth across diverse polypharmacy panels (included eval script: `scripts/eval_drugbank.py`).

---

### 3. Clinical AI Reliability Benchmarking
**Problem:** The research community lacks a reproducible, open framework for measuring how well LLMs perform clinical reasoning — and where they fail. Papers benchmark on USMLE but don't disclose prompting strategy, confidence calibration, or failure modes.

**How medagent-core helps:**
- Ships `scripts/eval_medqa.py`: runs the full agent pipeline on MedQA USMLE-style questions
- Logs per-question reasoning traces (not just accuracy), enabling qualitative failure analysis
- Compares reasoning quality across Claude, GPT-4o, Gemini, and Kimi with the same prompt
- Bayesian confidence score lets you measure calibration (does high confidence correlate with correct answers?)
- ESCALATE events reveal what the model *doesn't know* — the most clinically important failure mode

```bash
# Benchmark GPT-4o vs Claude on 100 USMLE questions:
ANTHROPIC_API_KEY=... python scripts/eval_medqa.py --max-samples 100
OPENAI_API_KEY=...   python scripts/eval_medqa.py --max-samples 100
# Compare results/medqa_eval.json across runs
```

---

### 4. Drug Discovery Literature Mining
**Problem:** Biomedical researchers need to rapidly synthesise evidence across hundreds of PubMed papers when evaluating a drug candidate or mechanism of action. Manual literature review takes weeks; generic RAG pipelines lack biomedical domain awareness.

**How medagent-core helps:**
- Extracts MeSH terms from clinical entities using scispaCy NER
- Queries PubMed ESearch/EFetch with structured MeSH queries (not keyword search)
- Hybrid BM25 + dense retrieval over a local corpus of ingested abstracts
- Evidence chain builder annotates which retrieved papers support each hypothesis
- All evidence is source-attributed for citation in papers

```bash
# Ingest recent PubMed abstracts on a target mechanism:
python scripts/ingest_kb.py --pubmed-terms "KRAS G12C inhibitor" "MAPK pathway" --max-per-term 50

# Then query the agent:
POST /analyze
{ "query": "What is the evidence for sotorasib resistance mechanisms in KRAS G12C NSCLC?" }
```

---

### 5. Health-AI Pipeline Development — Reference Architecture
**Problem:** Every health-AI engineering team rebuilds the same safety infrastructure from scratch: PII de-identification, LLM fallback chains, output validation, audit logging, confidence gating. This is months of work, re-done repeatedly, with inconsistent safety guarantees.

**How medagent-core helps — use it as your starting point:**
- **Swap the LLM:** add a new adapter in `src/medagent/llm/adapters.py` (single class, ~50 lines)
- **Add a retrieval source:** implement `async search() → list[RetrievedDocument]` in `src/medagent/retrieval/`
- **Extend safety rules:** add regex patterns to `ScopeEnforcer` or `MedicalOutputValidator`
- **Change the state machine:** modify `VALID_TRANSITIONS` in `ClinicalAgentStateMachine`
- **Use the audit log:** every run is persisted to SQLite/Postgres with full intermediate state

All safety infrastructure (PII hashing, disclaimer injection, dual-source drug validation, ESCALATE gating) is production-hardened and covered by 93 unit tests.

---

### 6. AI Safety Research in High-Stakes Domains
**Problem:** AI safety researchers studying failure modes in high-stakes applications need realistic, instrumented systems where agent behaviour can be inspected, modified, and benchmarked. Most clinical AI is closed-source.

**How medagent-core helps:**
- The ESCALATE mechanism is a studied safety pattern: what triggers it, what happens after, and whether it correctly identifies genuine uncertainty
- PII hashing with configurable salts enables privacy-preserving research on real cohort data
- Every state transition, confidence score, evidence item, and uncertainty flag is persisted
- Jailbreak detection patterns in `ScopeEnforcer` can be extended and stress-tested
- The full audit log enables post-hoc analysis of adversarial inputs

---

### 7. Medical Education and Training Tool Development
**Problem:** Medical students learning clinical reasoning struggle to understand *why* a diagnosis is ranked above another — the reasoning chain is implicit in a clinician's head. AI-generated explicit differential reasoning chains could be a novel educational resource.

**How medagent-core helps:**
- Returns ranked hypotheses with evidence FOR and AGAINST each — the exact structure of clinical case discussions
- Uncertainty flags teach students what makes a case ambiguous
- ESCALATE trigger teaches the "know what you don't know" principle
- Eval scripts support USMLE-style case analysis at scale

---

## Architecture — Observe → Decide → Act

```
┌─────────────────────────────────────────────────────────────────────┐
│  POST /analyze (FHIR patient context + clinical query)              │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
        ┌───────────────────▼───────────────────────┐
        │       ClinicalAgentStateMachine            │
        │                                            │
        │  INTAKE ──► ENTITY_EXTRACTION              │
        │                    │                       │
        │          KNOWLEDGE_RETRIEVAL               │
        │         /     │          \                 │
        │      PubMed  DrugDB   LocalKB              │
        │         \     │          /                 │
        │          REASONING (LLM)                   │
        │                │                           │
        │         SAFETY_CHECK                       │
        │        /              \                    │
        │    OUTPUT          ESCALATE                │
        │  confidence≥0.6   confidence<0.6           │
        │                   or contradictions        │
        └────────────────────────────────────────────┘
                            │
                    audit_log.db (every run)
```

| Stage | What happens | Timeout |
|---|---|---|
| **INTAKE** | Scope enforcement; PII hashing at boundary | — |
| **ENTITY_EXTRACTION** | scispaCy NER on chief complaint + notes | 10s |
| **KNOWLEDGE_RETRIEVAL** | PubMed + RxNorm/OpenFDA + local KB (parallel) | 20s/source |
| **REASONING** | LLM generates hypotheses with evidence chains | 90s |
| **SAFETY_CHECK** | Confidence gate + contradiction detection | — |
| **OUTPUT / ESCALATE** | Structured response + mandatory disclaimer | — |

---

## Safety Design

Eight safety controls are **technically enforced in code** — not just policy:

| Control | Where | What it does |
|---|---|---|
| Mandatory disclaimer | `models.py` | Injected at construction time; cannot be overridden |
| Medical system prompt | `safety/disclaimer.py` | Prohibits prescriptions, code exec, internet access |
| Output validation | `llm/validator.py` | Rejects prescription language before returning |
| ESCALATE gate | `agent/state_machine.py` | Auto-escalates when confidence < 0.6 |
| PII hashing | `safety/pii_hasher.py` | HMAC-SHA256 before any LLM call |
| Scope enforcement | `safety/scope_enforcer.py` | Rejects 12 prohibited query patterns |
| Dual-source drug validation | `models.py` + `retrieval/drug_interaction.py` | Pydantic enforces ≥2 sources |
| Hard timeouts | `api/main.py` + `agent/` | 120s total, per-stage limits |

See [SAFETY.md](SAFETY.md) for the full policy.

---

## Quick Start

```bash
git clone https://github.com/Francis1998/medagent-core
cd medagent-core
pip install -e ".[dev]"
cp .env.example .env             # add at least one LLM API key
python scripts/ingest_kb.py --sample
uvicorn medagent.api.main:app --reload
```

Then try the live demo (no API keys needed):
```bash
python scripts/demo.py --case all
```

See [QUICKSTART.md](QUICKSTART.md) for Docker Compose and full curl examples.

---

## Run the Demos

```bash
# Chest pain / STEMI differential diagnosis
python scripts/demo.py --case chest_pain_mi

# Polypharmacy interaction screening (warfarin + amiodarone)
python scripts/demo.py --case drug_interaction

# Ambiguous B-symptoms → ESCALATE trigger
python scripts/demo.py --case escalate

# All three cases in sequence
python scripts/demo.py --case all
```

---

## API

### `POST /analyze` — Full clinical reasoning
```json
{
  "patient_context": {
    "patient_id_hash": "<sha256 of MRN>",
    "age": 65, "sex": "male",
    "chief_complaint": "Chest pain radiating to left arm",
    "clinical_notes": "2h history of crushing substernal pain...",
    "medications": [{"name": "aspirin"}, {"name": "metoprolol"}],
    "lab_results": [{"test_name": "Troponin I", "value": "2.4", "unit": "ng/mL", "abnormal": true}]
  },
  "query": "What is the differential diagnosis?"
}
```

**Response includes:**
- `ranked_hypotheses` — differential with Bayesian scores and evidence chains
- `drug_interactions_flagged` — dual-validated interaction warnings
- `overall_confidence` — calibrated confidence (triggers ESCALATE if < 0.6)
- `escalated` — true if human review is required
- `evidence_chain` — source documents supporting the reasoning
- `uncertainty_flags` — what made the model uncertain
- `recommended_next_steps` — actionable guidance
- `disclaimer` — mandatory safety disclaimer (always present)

### `POST /drug-interactions` — Targeted interaction check
```json
{ "medications": [{"name": "warfarin"}, {"name": "amiodarone"}, {"name": "aspirin"}] }
```

### `GET /health` — Readiness probe

---

## Benchmarks

```bash
# MedQA USMLE accuracy (100 questions, demo mode without data file)
python scripts/eval_medqa.py --max-samples 3

# DrugBank F1 / Precision / Recall
python scripts/eval_drugbank.py
```

Results saved to `results/`. Benchmark on your own data by providing `--data-path`.

---

## Quality Gates

All PRs must pass:

```bash
ruff check src/     # ✓ zero errors
pytest tests/ -v    # ✓ 93/93 passed
```

CI runs: lint → test → eval smoke test → Docker build (see [`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

---

## Repository Structure

```
medagent-core/
├── src/medagent/
│   ├── agent/          # State machine + durable audit log
│   ├── extraction/     # scispaCy NER + FHIR R4 parser
│   ├── retrieval/      # PubMed + RxNorm/OpenFDA + local KB hybrid
│   ├── reasoning/      # Bayesian scorer + LLM reasoning engine
│   ├── llm/            # Adapters (OpenAI/Anthropic/Google/Kimi) + router + validator
│   ├── safety/         # PII hashing + scope enforcer + disclaimers
│   └── api/            # FastAPI: /analyze /drug-interactions /health
├── tests/              # 93 pytest tests (all annotated + docstrings)
├── scripts/
│   ├── demo.py         # Rich interactive demo (no API keys needed)
│   ├── eval_medqa.py   # USMLE benchmark runner
│   ├── eval_drugbank.py# Drug interaction F1 evaluator
│   └── ingest_kb.py    # KB ingestion from JSONL or PubMed
├── assets/             # SVG demo animations for README
├── data/               # Sample FHIR bundle + KB index
├── results/            # Benchmark outputs
├── .github/workflows/  # CI: ruff + mypy + pytest + Docker
├── docker-compose.yml
├── Dockerfile
├── QUICKSTART.md       # 5-minute setup guide
├── CONFIGURATION.md    # Full env-var reference
├── SAFETY.md           # Safety policy + hard constraints
└── ARCHITECTURE.md     # FSM design + module map
```

---

## Extending the System

### Add a new LLM provider
```python
# src/medagent/llm/adapters.py
class MyProviderAdapter(BaseLLMAdapter):
    @property
    def provider_name(self) -> str:
        return "myprovider"

    async def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        # Call your provider's API
        ...
```

Register in `MedicalRouter.from_settings()` and it automatically joins the fallback chain.

### Add a new retrieval source
```python
# src/medagent/retrieval/my_source.py
async def search(entities: list[ClinicalEntity]) -> list[RetrievedDocument]:
    ...
```

Add to `RetrievalOrchestrator.retrieve()` — it will run in parallel with existing sources.

### Adjust safety thresholds
```bash
# .env
AGENT_CONFIDENCE_THRESHOLD=0.7   # more conservative escalation
AGENT_REASONING_TIMEOUT=60       # faster timeout for latency-sensitive apps
```

---

## Research Context

This project directly extends published research on:
- **AI-assisted drug discovery** — hybrid retrieval for biomedical literature
- **LLM calibration in clinical settings** — confidence scoring and escalation
- **Agentic AI safety patterns** — explicit FSM vs implicit chain-of-thought
- **Biomedical NLP** — scispaCy NER in clinical decision support pipelines

If you use this work in research, please cite this repository and link to [https://github.com/Francis1998/medagent-core](https://github.com/Francis1998/medagent-core).

---

## Contributing

Contributions welcome. Please:
1. Open an issue before large PRs
2. Tag safety-relevant issues with `safety-critical`
3. All new code requires type annotations, docstrings, and tests
4. Run `ruff check src/ && pytest tests/` before submitting

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

## Disclaimer

**This software is provided for research and educational purposes only. It is NOT intended for clinical use, medical diagnosis, or treatment planning. It has NOT been evaluated, validated, or cleared by any regulatory authority including the U.S. FDA or EMA. Do NOT use this system to make clinical decisions. Always consult a qualified healthcare professional.**
