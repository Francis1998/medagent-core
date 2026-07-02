# ARCHITECTURE.md — medagent-core System Architecture

## Overview

`medagent-core` is a safety-first clinical AI reasoning agent built around an explicit finite state machine. Unlike black-box LLM wrappers, every reasoning step is logged, every state transition is validated, and every output carries a mandatory audit trail.

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI REST Layer                    │
│         /analyze  /drug-interactions  /health           │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│             ClinicalAgentStateMachine                    │
│                                                          │
│  INTAKE ──► ENTITY_EXTRACTION ──► KNOWLEDGE_RETRIEVAL   │
│                                          │               │
│            ┌─────────────────────────────▼              │
│            │         REASONING                          │
│            └──────────────┬────────────────────         │
│                           │                             │
│                    SAFETY_CHECK                         │
│                  ┌────────┴────────┐                    │
│              OUTPUT           ESCALATE                  │
│                                                          │
│                    ERROR (any state)                    │
└──────────────────────────────────────────────────────────┘
```

---

## Module Map

```
src/medagent/
├── config.py          # Pydantic-settings: all env vars in one place
├── models.py          # Frozen Pydantic domain models (ClinicalQuery, ClinicalReasoning, …)
├── logging_config.py  # structlog JSON logging configuration
│
├── agent/
│   ├── state_machine.py   # ClinicalAgentStateMachine — state transitions
│   └── audit.py           # SQLAlchemy async audit log (persist_run, fetch_run)
│
├── extraction/
│   ├── ner.py             # EntityExtractor: scispaCy NER + regex fallback
│   └── fhir_parser.py     # FHIR R4 Bundle → FHIRPatientContext; PII hashing at boundary
│
├── retrieval/
│   ├── pubmed.py          # PubMed ESearch/EFetch async client (tenacity retries)
│   ├── drug_interaction.py # DrugInteractionClient: RxNorm + OpenFDA dual-source validation
│   ├── local_kb.py        # LocalKnowledgeBase: BM25 + dense hybrid retrieval
│   └── orchestrator.py    # RetrievalOrchestrator: parallel fan-out + deduplication
│
├── reasoning/
│   ├── bayesian.py        # bayesian_score, rank_hypotheses, calibrate_confidence
│   └── engine.py          # ReasoningEngine: LLM prompt → Hypothesis list
│
├── llm/
│   ├── base.py            # BaseLLMAdapter ABC + LLMResponse dataclass
│   ├── adapters.py        # OpenAI, Anthropic, Google, Kimi concrete adapters
│   ├── router.py          # MedicalRouter: task-to-provider routing with fallback chain
│   └── validator.py       # MedicalOutputValidator: prohibited content detection
│
├── safety/
│   ├── disclaimer.py      # Mandatory disclaimer strings + MEDICAL_SYSTEM_PROMPT
│   ├── pii_hasher.py      # HMAC-SHA256 PII hashing; redact_fhir_pii
│   └── scope_enforcer.py  # ScopeEnforcer: prohibited pattern detection + jailbreak stripping
│
└── api/
    ├── main.py            # FastAPI app, lifespan, /analyze, /drug-interactions, /health
    └── schemas.py         # API-layer request/response schemas (separate from domain models)
```

---

## State Machine — Detailed Flow

### INTAKE
- `ScopeEnforcer.check_query_in_scope()` validates the query
- Transition: → `ENTITY_EXTRACTION` | `ERROR`

### ENTITY_EXTRACTION
- `EntityExtractor.extract()` runs scispaCy NER (or regex fallback) on chief_complaint + clinical_notes
- Timeout: 10 seconds (configurable)
- Transition: → `KNOWLEDGE_RETRIEVAL` | `ERROR`

### KNOWLEDGE_RETRIEVAL
- `RetrievalOrchestrator.retrieve()` fans out to three sources in parallel:
  - **PubMed**: ESearch by MeSH terms derived from entities → EFetch abstracts
  - **RxNorm + OpenFDA**: Pairwise drug interaction checks (dual-source validation)
  - **Local KB**: Hybrid BM25 + dense retrieval over local JSONL corpus
- MeSH terms (`EntityExtractor.get_mesh_terms`) are derived in **deterministic**
  first-seen entity order. The orchestrator queries only `mesh_terms[:5]`, so a
  stable order guarantees the same PubMed subset — and therefore reproducible
  retrieval — for identical inputs.
- Timeout: 20 seconds per source (configurable)
- Transition: → `REASONING` | `ERROR`

### REASONING
- `ReasoningEngine.reason()` constructs a structured prompt with entities + evidence snippets
- `MedicalRouter.route_differential()` dispatches to the optimal LLM (Claude preferred for complex differential)
- LLM response parsed into `Hypothesis` objects with evidence_for / evidence_against lists
- `rank_hypotheses()` applies Bayesian scoring and sorts by posterior probability
- Timeout: 90 seconds (configurable)
- Transition: → `SAFETY_CHECK` | `ERROR`

### SAFETY_CHECK
- Computes `overall_confidence` from top-3 hypothesis scores via `calibrate_confidence()`
- Checks for contradictory evidence (strong FOR + strong AGAINST on same hypothesis)
- Transition:
  - If `confidence < threshold` OR contradictory evidence → `ESCALATE`
  - Otherwise → `OUTPUT`

### OUTPUT / ESCALATE
- Constructs `ClinicalReasoning` with all intermediate results + mandatory disclaimer
- `ESCALATE` always sets `escalated=True` and includes human-review instructions
- Audit log written asynchronously via `persist_run()`

---

## Multi-LLM Routing

| Task | Preferred Provider | Fallback Chain | Rationale |
|---|---|---|---|
| Differential diagnosis | Claude Sonnet 4.6 | GPT-5.5 → Gemini → Kimi | Best long-form reasoning |
| Drug interaction lookup | GPT-5.5 | Claude → Gemini → Kimi | Best structured JSON adherence |
| Entity resolution | Gemini 3.1 Pro | GPT-5.5 → Claude → Kimi | Fastest for short classification |

All responses pass through `MedicalOutputValidator` before returning. If the validator rejects the response (prohibited prescription language), the fallback chain is tried automatically.

---

## Hybrid Retrieval

```
Query (entities + free text)
         │
    ┌────▼────┐     ┌─────────────┐
    │  BM25   │     │  Dense vec  │
    │ (sparse)│     │ (BioWordVec)│
    └────┬────┘     └──────┬──────┘
         │                 │
         └────── α ─────── ┘
                 │
           linear combo
                 │
           Reranked top-k
```

- **α = 0.5** (equal weight): configurable in `LocalKnowledgeBase(alpha=...)`
- Dense embeddings: requires `data/biowordvec_pubmed_mesh_200d.bin` (download separately)
- Without embeddings: falls back to BM25-only automatically

---

## Data Flow and PII Boundary

```
Raw FHIR Bundle (with PII)
        │
FHIRPatientContext constructor
        │  hash(name, MRN, DOB) → patient_id_hash
        │  raw_fhir stored for audit only
        │
FHIRPatientContext (no raw PII in fields)
        │
ClinicalQuery.patient_context
        │
Agent State Machine
        │  Only hashed IDs, clinical text, labs, and meds passed to LLMs
        │  sanitise_clinical_text() scrubs text fields before LLM dispatch
        │
LLM (no PII exposure)
```

---

## Confidence Calibration

The overall confidence score follows a Platt scaling approximation:

```
log_odds_posterior = log_odds_prior + Σ log(strength_FOR) − Σ log(strength_AGAINST)
posterior = sigmoid(log_odds_posterior)

calibrated_confidence = mean(top_3_scores) × (1 − 0.3 × entropy_penalty)
```

Where `entropy_penalty` = normalised Shannon entropy over the top-3 scores. High entropy (all hypotheses equally likely) reduces the confidence score, reflecting genuine uncertainty.

---

## Audit Log Schema

```sql
CREATE TABLE audit_log (
    id                    INTEGER PRIMARY KEY,
    session_id            TEXT NOT NULL,           -- UUID
    inputs_hash           TEXT,                    -- SHA-256 for dedup
    query_text            TEXT NOT NULL,
    state_reached         TEXT NOT NULL,           -- AgentState enum
    escalated             BOOLEAN NOT NULL,
    overall_confidence    FLOAT NOT NULL,
    model_used            TEXT,
    wall_time_seconds     FLOAT,
    hypotheses_json       TEXT,                    -- JSON array
    interactions_json     TEXT,                    -- JSON array
    uncertainty_flags_json TEXT,                   -- JSON array
    entities_json         TEXT,                    -- JSON array
    created_at            DATETIME NOT NULL
);
```

---

## Extension Points

- **Add a new LLM provider**: Implement `BaseLLMAdapter` in `src/medagent/llm/adapters.py` and register in `MedicalRouter.from_settings()`
- **Add a new retrieval source**: Implement `async search() → list[RetrievedDocument]` and add to `RetrievalOrchestrator.retrieve()`
- **Customise confidence threshold**: Set `AGENT_CONFIDENCE_THRESHOLD` in `.env`
- **Extend safety rules**: Add regex patterns to `ScopeEnforcer` or `MedicalOutputValidator`
- **Custom NER model**: Pass a different `model_name` to `EntityExtractor` (any scispaCy-compatible model)
