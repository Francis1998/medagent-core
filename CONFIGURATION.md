# CONFIGURATION.md — medagent-core Configuration Reference

All configuration is managed through environment variables loaded from a `.env` file (see `.env.example`). Values are validated at startup via Pydantic settings — the server will refuse to start if required values are malformed.

---

## LLM API Keys

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Recommended | OpenAI API key (GPT-4o) |
| `ANTHROPIC_API_KEY` | Recommended | Anthropic API key (Claude 3.5 Sonnet) |
| `GOOGLE_API_KEY` | Optional | Google Generative AI key (Gemini) |
| `KIMI_API_KEY` | Optional | Kimi/Moonshot API key |

The agent falls back gracefully — if Claude is unavailable it routes to GPT-4o, then Gemini, then Kimi. With no keys configured, the reasoning engine uses heuristic-only fallback (lower accuracy).

## LLM Model Overrides

| Variable | Default | Description |
|---|---|---|
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model name |
| `ANTHROPIC_MODEL` | `claude-3-5-sonnet-20241022` | Anthropic model name |
| `GOOGLE_MODEL` | `gemini-1.5-pro` | Google model name |
| `KIMI_MODEL` | `moonshot-v1-32k` | Kimi model name |

## External APIs

| Variable | Required | Description |
|---|---|---|
| `PUBMED_API_KEY` | Optional | NCBI API key (raises rate limit from 3 to 10 req/s) |
| `PUBMED_EMAIL` | Optional | Required by NCBI ToS for unauthenticated requests |
| `OPENFDA_API_KEY` | Optional | OpenFDA API key (extends rate limits) |

## Database

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/audit.db` | SQLAlchemy async DB URL |

For production, use PostgreSQL:
```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/medagent
```

## Agent Behaviour

| Variable | Default | Description |
|---|---|---|
| `AGENT_CONFIDENCE_THRESHOLD` | `0.6` | Minimum confidence before ESCALATE |
| `AGENT_TOTAL_TIMEOUT_SECONDS` | `120` | Hard wall-clock cap per run |
| `AGENT_ENTITY_EXTRACTION_TIMEOUT` | `10` | Extraction stage timeout |
| `AGENT_RETRIEVAL_TIMEOUT` | `20` | Per-source retrieval timeout |
| `AGENT_REASONING_TIMEOUT` | `90` | LLM reasoning call timeout |

## Knowledge Base

| Variable | Default | Description |
|---|---|---|
| `KB_EMBEDDING_PATH` | `./data/biowordvec_pubmed_mesh_200d.bin` | Path to BioWordVec embeddings (optional) |
| `KB_INDEX_PATH` | `./data/kb_index/` | Path to the local KB index directory |

The local KB requires a `docs.jsonl` file in `KB_INDEX_PATH`. Build the sample index with:
```bash
python scripts/ingest_kb.py --sample
```

## API Server

| Variable | Default | Description |
|---|---|---|
| `API_HOST` | `0.0.0.0` | Bind host |
| `API_PORT` | `8000` | Bind port |
| `API_WORKERS` | `1` | Uvicorn workers (increase for production) |
| `LOG_LEVEL` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

## Security

| Variable | Default | Description |
|---|---|---|
| `PII_HASH_SALT` | `insecure-default-change-me` | HMAC-SHA256 salt for PII hashing |

**Always change `PII_HASH_SALT` in production.** Generate a secure value with:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Evaluation

| Variable | Default | Description |
|---|---|---|
| `MEDQA_DATA_PATH` | `./data/medqa_usmle_4_options_test.jsonl` | MedQA test file |
| `DRUGBANK_TEST_PATH` | `./data/drugbank_interactions_test.json` | DrugBank test file |
| `EVAL_MAX_SAMPLES` | `100` | Maximum samples for benchmark runs |
