# CONFIGURATION.md — medagent-core Configuration Reference

All configuration is managed through environment variables loaded from a `.env` file (see `.env.example`). Values are validated at startup via Pydantic settings — the server will refuse to start if required values are malformed.

---

## LLM API Keys

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Recommended | OpenAI API key (GPT-6.1 Sol) |
| `ANTHROPIC_API_KEY` | Recommended | Anthropic API key (Claude Opus 5.5) |
| `GOOGLE_API_KEY` | Optional | Google AI Studio key (Gemini 4 Argon; Argon and Carbon need a paid-tier key) |
| `KIMI_API_KEY` | Optional | Kimi/Moonshot API key (Kimi K3.1 Pro) |

The agent falls back gracefully — for a differential diagnosis, if Claude is unavailable it routes to GPT-6.1 Sol, then Gemini, then Kimi. With no keys configured, the reasoning engine uses heuristic-only fallback (lower accuracy).

## LLM Model Overrides

| Variable | Default | Description |
|---|---|---|
| `OPENAI_MODEL` | `gpt-6.1-sol` | OpenAI model name |
| `ANTHROPIC_MODEL` | `claude-opus-5-5` | Anthropic model name |
| `GOOGLE_MODEL` | `gemini-4-argon` | Google model name |
| `KIMI_MODEL` | `kimi-k3.1-pro` | Kimi model name |
| `KIMI_BASE_URL` | `https://api.moonshot.ai/v1` | Kimi OpenAI-compatible endpoint (`https://api.moonshot.cn/v1` for mainland China accounts) |
| `LLM_MAX_OUTPUT_TOKENS` | `32768` | Completion budget per call, **including reasoning/thinking tokens** |

### Why these defaults (verified 2026-11-12)

Every alternative below gets the same request shaping as its provider's default (see
[Sampling-parameter compatibility](#sampling-parameter-compatibility)); set it with the matching
`*_MODEL` variable.

| Provider | Default | Why | Alternatives |
|---|---|---|---|
| OpenAI | `gpt-6.1-sol` | Near-Astra reasoning at a fifth of Astra's price ($2 / $10 vs $10 / $50); OpenAI's choice for balancing intelligence and cost; Chat Completions without tools is supported | `gpt-6-astra` (flagship, $10 / $50), `gpt-6.1-terra` ($1 / $5) and `gpt-6-luna` ($0.10 / $0.50) for faster, cheaper calls — [models](https://developers.openai.com/api/docs/models) |
| Anthropic | `claude-opus-5-5` | Anthropic's recommended starting point for most workloads and medagent's preferred model for differential diagnosis; adaptive thinking ($4 / $20) | `claude-fable-5-2` (new; for demanding reasoning and long-horizon agentic work, $8 / $40, 1M context, 128K output; supersedes `claude-fable-5-1`; requires 30-day data retention, so it is not available under zero data retention), `claude-sonnet-5-5` ($2 / $10), `claude-haiku-5-5` (from $0.10 / $0.50) — [models](https://platform.claude.com/docs/en/models/overview), [Fable 5.2](https://platform.claude.com/docs/en/models/fable-5-2/overview) |
| Google | `gemini-4-argon` | Flagship reasoning with fewer thinking tokens per turn than Carbon ($2 / $10 through 2026-11-30, $4 / $20 from 2026-12-01) | `gemini-4-carbon` (strongest reasoning, same price, more thinking per turn), `gemini-4-hydrogen` (new; fast Gemini 4 and the lower-latency choice, $1.50 / $7.50), `gemini-3.8-flash` (previous-generation Flash, $0.75 / $3.75 through 2026-12-31, then $1.50 / $7.50) — [models](https://aistudio.google.com/docs/models), [Hydrogen](https://aistudio.google.com/docs/whats-new-gemini-4-hydrogen), [pricing](https://aistudio.google.com/docs/pricing) |
| Kimi | `kimi-k3.1-pro` | Kimi's flagship ($2 / $10, 1,048,576-token context); the K2 series closed to new users on 2026-10-31 and retires by the end of December 2026 | `kimi-k3.1-pro-highspeed` (2–3× faster, $4 / $20), `kimi-k3` ($3 / $15) — [quickstart](https://platform.kimi.ai/docs/guide/kimi-k3-1-pro-quickstart.md), [pricing](https://platform.kimi.ai/docs/pricing/chat.md) |

Prices are per 1M input / output tokens from the linked provider pages and change over time.

Anthropic still recommends starting with Claude Opus 5.5 and moving to Claude Fable 5.2 only when
Opus at higher effort falls short in your evaluations, so Opus 5.5 stays the default. For a faster
Gemini, set `GOOGLE_MODEL=gemini-4-hydrogen`. Google recommends it as the upgrade from Gemini 3.8
Flash and reports more than 5× fewer fabricated claims, which matters because the Gemini slot also
answers differential diagnoses whenever Claude and OpenAI are unavailable. It therefore replaces
`gemini-3.8-flash` as the documented lower-latency option. medagent sends no `thinking_level`, so
Hydrogen runs at its default `high`; Google still rates it Fast (Argon: Moderate).
`gemini-3.8-flash` keeps working and costs half as much until its price rises to Hydrogen's on
2027-01-01. Hydrogen also has a free tier, but Google may use free-tier prompts to improve its
products, so use a paid key for research data.

### Sampling-parameter compatibility

Current reasoning models fix or reject sampling parameters, so each adapter shapes its request
per model (`accepts_temperature()` in `src/medagent/llm/adapters.py`): the clinical
`temperature=0.1` is sent only where the provider allows it, and no adapter ever sends `top_p`,
`top_k`, `logprobs` or `top_logprobs`. Model families are matched on the final path segment of the
id, so a resource name such as `models/gemini-4-hydrogen` is shaped like `gemini-4-hydrogen`. No
adapter sends a thinking or reasoning-effort setting either, so each model keeps its default.
Switching to any model below cannot trigger a sampling-parameter `400`.

| Family | Provider rule | medagent |
|---|---|---|
| Claude (every model) | `400` for `temperature`, `top_p` or `top_k` on every model since API version 2026-10-21, and for any non-default value on the Claude 5.5 family (`claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`) and Claude Fable 5.x (`claude-fable-5-2`, `claude-fable-5-1`); `output_config.effort` is the supported knob. Claude Fable 5.2 also returns `400` for `thinking` set to `enabled` or `disabled` (adaptive thinking is always on) | never sent; `thinking` is omitted too |
| OpenAI GPT-5+/o-series | `temperature`, `top_p`, `top_logprobs` (and `logprobs` on Chat Completions) rejected unless reasoning effort is `none`; GPT-6.1 Sol / GPT-6 Astra support only `low`…`max`, GPT-6.1 Terra / GPT-6 Luna accept `none` | omitted (no `reasoning_effort` is sent, so the model default applies); budget sent as `max_completion_tokens` |
| Gemini 3.x / Gemini 4 (incl. `gemini-3.8-flash`, `gemini-4-argon`, `gemini-4-carbon`, `gemini-4-hydrogen`) | Google says to remove `temperature`, `top_p` and `top_k`; if provided they are ignored. Default thinking level is `medium` on Carbon and Argon and `high` on Hydrogen, which rejects `minimal` | omitted; no thinking config is sent |
| Kimi K2.6 / K2.7 / K3 series | `temperature` is fixed (`1.0`; `kimi-k2.6` uses `0.6` with thinking off); other values return an error (`reasoning_effort` `low`/`high`/`max` is the K3 knob) | omitted |
| Older models (e.g. `gpt-4.1`, Gemini 2.5) | Accept sampling parameters. From 2026-12-01 Google serves `gemini-2.5-pro` requests with `gemini-3.8-flash` (and `gemini-2.5-flash` with `gemini-3.5-flash-lite`), which ignore the temperature. Kimi's `moonshot-v1` and original K2 preview models are already retired | `temperature=0.1` |

Sources: Anthropic [sampling parameters](https://platform.claude.com/docs/en/build-with-claude/thinking.md),
[Claude Fable 5.2](https://platform.claude.com/docs/en/models/fable-5-2/whats-new-fable-5-2),
[Claude Sonnet 5.5](https://platform.claude.com/docs/en/models/sonnet-5-5/overview.md) and
[effort](https://platform.claude.com/docs/en/build-with-claude/effort.md); OpenAI
[GPT-6 unsupported parameters](https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra.md);
Google [Gemini 4 Hydrogen migration checklist](https://aistudio.google.com/docs/whats-new-gemini-4-hydrogen#migration-checklist),
[latest models](https://aistudio.google.com/docs/latest-model) and
[Gemini 2.5 routing](https://aistudio.google.com/docs/models#gemini-25-pro); Kimi
[parameter reference](https://platform.kimi.ai/docs/api/models-overview).

Reasoning and thinking tokens count against the completion budget, so `LLM_MAX_OUTPUT_TOKENS`
defaults to 32,768. Google recommends at least that for Gemini 4 Argon and Carbon, and it is also
their per-hop cap for non-streaming calls (Hydrogen: 65,536), so a default request completes in one
hop. Lower it only for older models with smaller output limits. Claude calls pass
`AGENT_REASONING_TIMEOUT` as an explicit client timeout, which the Anthropic SDK requires before it
accepts a non-streaming budget this large. Thinking blocks are never returned as the answer: the
adapter joins the text blocks, and a response with no text raises an adapter error so the router
falls back.

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
| `API_HOST` | `127.0.0.1` | Bind host |
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

## MCP Server

`medagent-mcp` reads these from the process environment (set them in the MCP host's `env` block;
they are not loaded from `.env`). It also uses `PII_HASH_SALT` above to hash patient references.

| Variable | Flag | Default | Description |
|---|---|---|---|
| `MEDAGENT_MCP_AUDIT_LOG` | `--audit-log PATH` | unset (off) | Append one JSON line per `tools/call` (hashes and counts only) |
| `MEDAGENT_MCP_LOG_LEVEL` | `--log-level LEVEL` | `WARNING` | STDERR log level; STDOUT is reserved for JSON-RPC |

See [docs/guides/MCP_SERVER_GUIDE.md](docs/guides/MCP_SERVER_GUIDE.md).

## CDS Hooks

The HL7 CDS Hooks 2.0 services under `/cds-services` are part of the API server and read these
settings from the environment or `.env`. They also use `PII_HASH_SALT` (hashed patient, user and
`hookInstance` ids in the audit trail) and `DATABASE_URL` (the `cds_hooks_audit` table).

| Variable | Default | Description |
|---|---|---|
| `MEDAGENT_CDS_HOOKS_CORS_ORIGINS` | empty (no CORS) | Comma-separated browser origins allowed to call `/cds-services` (CORS opt-in), e.g. `https://sandbox.cds-hooks.org`. Each entry must be `scheme://host[:port]`; wildcards and paths are rejected at startup. Applies to `/cds-services` paths only — the rest of the API keeps its app-wide CORS policy. |

The services do not verify CDS Hooks JWTs: run them only in research sandboxes, behind a gateway that
terminates TLS and authenticates the CDS client. See
[docs/guides/CDS_HOOKS_GUIDE.md](docs/guides/CDS_HOOKS_GUIDE.md).

## Evaluation

| Variable | Default | Description |
|---|---|---|
| `MEDQA_DATA_PATH` | `./data/medqa_usmle_4_options_test.jsonl` | MedQA test file |
| `DRUGBANK_TEST_PATH` | `./data/drugbank_interactions_test.json` | DrugBank test file |
| `EVAL_MAX_SAMPLES` | `100` | Maximum samples for benchmark runs |
