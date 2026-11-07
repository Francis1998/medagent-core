# CONFIGURATION.md — medagent-core Configuration Reference

All configuration is managed through environment variables loaded from a `.env` file (see `.env.example`). Values are validated at startup via Pydantic settings — the server will refuse to start if required values are malformed.

---

## LLM API Keys

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Recommended | OpenAI API key (GPT-6.1 Sol) |
| `ANTHROPIC_API_KEY` | Recommended | Anthropic API key (Claude Opus 5.5) |
| `GOOGLE_API_KEY` | Optional | Google AI Studio key (Gemini 4 Argon) |
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

### Why these defaults (verified 2026-11-06)

| Provider | Default | Why | Alternatives |
|---|---|---|---|
| OpenAI | `gpt-6.1-sol` | Near-Astra reasoning at a fifth of Astra's price ($2 / $10 vs $10 / $50 per 1M input/output tokens); Chat Completions without tools is supported | `gpt-6-astra` (highest intelligence), `gpt-6.1-terra` / `gpt-6-luna` (faster, cheaper) — [models](https://developers.openai.com/api/docs/models) |
| Anthropic | `claude-opus-5-5` | Anthropic's recommended default and medagent's preferred model for differential diagnosis; adaptive thinking ($4 / $20) | `claude-sonnet-5-5` (faster, $2 / $10), `claude-fable-5-1` (demanding long-horizon work) — [models](https://platform.claude.com/docs/en/models/overview) |
| Google | `gemini-4-argon` | Flagship reasoning model ($2 / $10 through 2026-11-30, $4 / $20 from 2026-12-01) | `gemini-3.8-flash` for latency-sensitive entity resolution — [models](https://aistudio.google.com/docs/models), [pricing](https://aistudio.google.com/docs/pricing) |
| Kimi | `kimi-k3.1-pro` | Kimi's flagship (1M context); Kimi K2 is being retired (closed to new users from 2026-10-31, full retirement planned by end of 2026) | `kimi-k3.1-pro-highspeed` (2–3× faster) — [quickstart](https://platform.kimi.ai/docs/guide/kimi-k3-1-pro-quickstart.md), [pricing](https://platform.kimi.ai/docs/pricing/chat.md) |

Prices are per 1M input / output tokens from the linked provider pages and change over time.

### Sampling-parameter compatibility

Current reasoning models fix or reject sampling parameters, so each adapter shapes its request
per model (`accepts_temperature()` in `src/medagent/llm/adapters.py`): the clinical
`temperature=0.1` is sent only where the provider allows it, and no adapter ever sends `top_p`,
`top_k`, `logprobs` or `top_logprobs`. Switching to any model below cannot trigger a
sampling-parameter `400`.

| Family | Provider rule | medagent |
|---|---|---|
| Claude (every model) | `400` for `temperature`, `top_p` or `top_k` on every model since API version 2026-10-21, and on the Claude 5.5 family (`claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`) and `claude-fable-5-1` for any non-default value; `output_config.effort` is the supported knob | never sent |
| OpenAI GPT-5+/o-series | `temperature`, `top_p`, `top_logprobs` (and `logprobs` on Chat Completions) rejected unless reasoning effort is `none`; GPT-6.1 Sol / GPT-6 Astra support only `low`…`max`, GPT-6.1 Terra / GPT-6 Luna accept `none` | omitted (no `reasoning_effort` is sent, so the model default applies); budget sent as `max_completion_tokens` |
| Gemini 3.x / Gemini 4 (incl. `gemini-3.8-flash`, `gemini-4-argon`) | Google says to remove `temperature`, `top_p` and `top_k`; if provided they are ignored | omitted |
| Kimi K2.6 / K2.7 / K3 series | `temperature` fixed at `1.0`; other values return an error (`reasoning_effort` `low`/`high`/`max` is the knob) | omitted |
| Older models (e.g. `gpt-4.1`, Gemini 2.5, Kimi K2 / `moonshot-v1`) | Accept sampling parameters | `temperature=0.1` |

Sources: Anthropic [sampling parameters](https://platform.claude.com/docs/en/build-with-claude/thinking.md),
[Claude Sonnet 5.5](https://platform.claude.com/docs/en/models/sonnet-5-5/overview.md) and
[effort](https://platform.claude.com/docs/en/build-with-claude/effort.md); OpenAI
[GPT-6 unsupported parameters](https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra.md);
Google [Gemini 3](https://aistudio.google.com/docs/gemini-3.md).

Reasoning and thinking tokens count against the completion budget, so `LLM_MAX_OUTPUT_TOKENS`
defaults to 32,768 (Google recommends at least 32,768 for Gemini 4 Argon). Lower it only for
older models with smaller output limits. Claude calls pass `AGENT_REASONING_TIMEOUT` as an
explicit client timeout, which the Anthropic SDK requires before it accepts a non-streaming
budget this large. Thinking blocks are never returned as the answer: the adapter joins the text
blocks, and a response with no text raises an adapter error so the router falls back.

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

## Evaluation

| Variable | Default | Description |
|---|---|---|
| `MEDQA_DATA_PATH` | `./data/medqa_usmle_4_options_test.jsonl` | MedQA test file |
| `DRUGBANK_TEST_PATH` | `./data/drugbank_interactions_test.json` | DrugBank test file |
| `EVAL_MAX_SAMPLES` | `100` | Maximum samples for benchmark runs |
