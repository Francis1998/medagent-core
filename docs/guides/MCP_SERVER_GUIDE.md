# MCP Server Guide

*medagent-core — dual-era Model Context Protocol server for the deterministic safety layer*

![medagent MCP server: a real stdio session in both protocol eras](../../assets/mcp_server_demo.gif)

> **⚠️ RESEARCH USE ONLY — NOT FDA-cleared — NOT for clinical deployment.** Every tool result
> carries the mandatory disclaimer. Findings are advisory for review by a licensed clinician;
> they are never prescriptions or treatment orders, and an empty result is not evidence of safety.

`medagent-mcp` exposes medagent's deterministic, offline safety checks to any
[Model Context Protocol](https://modelcontextprotocol.io) host — Claude Desktop, Claude Code,
Cursor, VS Code, the MCP Inspector — over **stdio**, using only the Python standard library for
JSON-RPC. It speaks both the current stateless protocol (**2026-07-28**) and the legacy
`initialize` handshake (**2025-11-25**, **2025-06-18**).

## Contents

- [Why this exists](#why-this-exists)
- [Tools at a glance](#tools-at-a-glance)
- [Install](#install)
- [Try it in 30 seconds](#try-it-in-30-seconds)
- [Connect a client](#connect-a-client)
- [Tool reference](#tool-reference)
- [Protocol and dual-era compatibility](#protocol-and-dual-era-compatibility)
- [Safety model](#safety-model)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Limitations](#limitations)
- [How this demo was recorded](#how-this-demo-was-recorded)

## Why this exists

[BioMCP](https://github.com/genomoncology/biomcp) and FHIR MCP servers such as
[wso2/fhir-mcp-server](https://github.com/wso2/fhir-mcp-server) let agents in Claude, Cursor or
VS Code *fetch* biomedical data — literature, trials, variants, EHR resources — over MCP. None of
them give the agent a deterministic way to *check a medication regimen* before it talks about it.
medagent already has that layer (allergy, pregnancy, renal/hepatic dosing, Beers, QT, serotonergic
and anticholinergic burden, boxed warnings and 80+ pairwise interaction rules), but it was only
reachable through medagent's own HTTP API, where `/analyze` needs LLM keys and `/drug-interactions`
calls RxNorm/OpenFDA over the network.

**Gap closed:** an agent can now pull a patient's FHIR R4 Bundle from any FHIR source, normalise and
de-identify it with `parse_fhir_bundle`, and run `screen_medications` on the result — offline,
deterministic, auditable, with the same disclaimers and scope enforcement as the rest of
medagent.

## Tools at a glance

| Tool | What it does | Needs |
| --- | --- | --- |
| `screen_medications` | Runs 7 patient-context checks (allergy, inter-class allergy, pregnancy, lactation, Beers 65+, renal eGFR, hepatic Child-Pugh), 6 medication-list checks (duplicate therapy, QT burden, anticholinergic burden, serotonergic load, boxed warnings, ACEI/ARB/ARNI duplication) and every offline interaction rule; reports which checks were skipped for missing context. | `medications`; optional `patient`, `patient_ref`, `include_interactions` |
| `check_drug_interactions` | Runs only the offline interaction rules: 80 pairwise checkers auto-discovered from `medagent.safety`, plus QTc pairs, anticoagulant-bleeding and triple-whammy combinations (83 today). | `medications` (2–50) |
| `parse_fhir_bundle` | FHIR R4 Bundle → de-identified context (HMAC-hashed patient id, age, sex, active medications, allergies, labs, vitals) and a `screening_input` object to pass straight to `screen_medications`. | `bundle` |
| `list_safety_controls` | Catalogue of the hard constraints (SAFETY.md §3.1–3.8) and every check the tools run, with SAFETY.md sections and required inputs. | optional `category`, `query` |

All four tools are annotated `readOnlyHint: true`, `destructiveHint: false`,
`idempotentHint: true`, `openWorldHint: false`, make no network or LLM calls, and keep no state
between requests. `tools/list` returns them in a deterministic (alphabetical) order.

## Install

Python 3.10+; no API keys or network access required.

```bash
git clone https://github.com/Francis1998/medagent-core
cd medagent-core
pip install -e .                # or: uv pip install -e .
medagent-mcp --version          # medagent-mcp 0.1.0 (MCP 2026-07-28, 2025-11-25, 2025-06-18)
python -m medagent.mcp --help   # same server, module entry point
```

Set a real salt before handling anything that resembles patient data — identifiers are hashed with
HMAC-SHA256 keyed by `PII_HASH_SALT`, and the server warns on stderr while the default is in use:

```bash
export PII_HASH_SALT="$(python -c 'import secrets; print(secrets.token_hex(32))')"
```

## Try it in 30 seconds

`scripts/mcp_stdio_demo.py` launches the server as a subprocess exactly like an MCP host and runs a
modern session (discover → list → parse a FHIR bundle → screen it → unsupported-version probe) and a
legacy `initialize` session:

```console
$ PII_HASH_SALT=demo-only-salt python scripts/mcp_stdio_demo.py
→ server/discover   (_meta protocolVersion 2026-07-28)
← medagent-core 0.1.0 · supportedVersions ['2026-07-28', '2025-11-25', '2025-06-18']
→ tools/call parse_fhir_bundle   (sample_fhir_bundle_polypharmacy.json)
← patient f60ae88463f3… (hashed) · age 81 · 4 active meds · egfr 28.0 · identifiers echoed: 0
→ tools/call screen_medications   (arguments = screening_input)
← 8 findings · highest CRITICAL · escalation_recommended=True
   CRITICAL statin_cyp3a4      Simvastatin 40 mg + Clarithromycin 500 mg
   HIGH     warfarin_nsaid     Warfarin 5 mg + Ibuprofen 400 mg
   ...
```

The full, unedited output is in [`mcp_server_demo_transcript.txt`](mcp_server_demo_transcript.txt).
The raw protocol is one JSON-RPC message per line:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"server/discover","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}}}}' \
  | medagent-mcp | jq '.result.supportedVersions'
```

## Connect a client

Use the **absolute path** of the `medagent-mcp` executable inside the environment where you
installed medagent (`which medagent-mcp`); GUI hosts do not inherit your shell's virtualenv.
Replace `/abs/path/medagent-core` below accordingly.

### Claude Desktop

Edit `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/`, Windows:
`%APPDATA%\Claude\`) and restart Claude Desktop:

```json
{
  "mcpServers": {
    "medagent": {
      "command": "/abs/path/medagent-core/.venv/bin/medagent-mcp",
      "args": ["--audit-log", "/abs/path/medagent-mcp-audit.jsonl"],
      "env": { "PII_HASH_SALT": "replace-with-a-long-random-secret" }
    }
  }
}
```

### Claude Code

```bash
claude mcp add --env PII_HASH_SALT=replace-with-a-long-random-secret --transport stdio medagent \
  -- /abs/path/medagent-core/.venv/bin/medagent-mcp --audit-log /abs/path/medagent-mcp-audit.jsonl
claude mcp list        # or /mcp inside a session
```

Keep at least one option (here `--transport stdio`) between `--env` and the server name; add
`--scope project` to share the entry through `.mcp.json`.

### Cursor

`~/.cursor/mcp.json` (all projects) or `.cursor/mcp.json` (one project):

```json
{
  "mcpServers": {
    "medagent": {
      "command": "/abs/path/medagent-core/.venv/bin/medagent-mcp",
      "env": { "PII_HASH_SALT": "replace-with-a-long-random-secret" }
    }
  }
}
```

### VS Code (agent mode)

`.vscode/mcp.json` in the workspace; the salt is prompted for and stored as a secret:

```json
{
  "inputs": [
    { "type": "promptString", "id": "pii-salt", "description": "medagent PII hash salt", "password": true }
  ],
  "servers": {
    "medagent": {
      "type": "stdio",
      "command": "${workspaceFolder}/.venv/bin/medagent-mcp",
      "args": ["--audit-log", "${workspaceFolder}/.medagent/mcp-audit.jsonl"],
      "env": { "PII_HASH_SALT": "${input:pii-salt}" }
    }
  }
}
```

### MCP Inspector (CLI)

Verified with `@modelcontextprotocol/inspector` 2.14.0, which can force either protocol era:

```bash
# Dual-era probe: the Inspector sends server/discover first and stays modern
npx @modelcontextprotocol/inspector --cli medagent-mcp --protocol-era auto \
  --method initialize --format json -q | jq -r .result.protocolVersion      # 2026-07-28
# Force the legacy initialize handshake
npx @modelcontextprotocol/inspector --cli medagent-mcp --protocol-era legacy \
  --method initialize --format json -q | jq -r .result.protocolVersion      # 2025-11-25
# Schema portability lint (OpenAPI/Gemini-style single-type dialects): 0 errors, 0 warnings
npx @modelcontextprotocol/inspector --cli medagent-mcp --method tools/list --strict --format json -q
# Call tools
npx @modelcontextprotocol/inspector --cli medagent-mcp --method tools/call \
  --tool-name check_drug_interactions --tool-arg 'medications=["warfarin 5 mg","fluconazole 150 mg"]'
npx @modelcontextprotocol/inspector --cli medagent-mcp --method tools/call \
  --tool-name parse_fhir_bundle --tool-args-json "{\"bundle\": $(cat data/sample_fhir_bundle_polypharmacy.json)}"
```

`npx @modelcontextprotocol/inspector medagent-mcp` (without `--cli`) opens the web UI.

## Tool reference

Every successful `tools/call` returns `structuredContent` that conforms to the tool's
`outputSchema`, plus two text blocks: a short human-readable summary that ends with the disclaimer,
and the serialized `structuredContent` (for clients that ignore structured output). Findings share
one shape:

| Field | Meaning |
| --- | --- |
| `check_id` | Stable id, e.g. `warfarin_nsaid`, `renal_dose` (see `list_safety_controls`) |
| `checker` | Existing medagent class that produced the finding |
| `category` | `patient_context`, `medication_list` or `interaction` |
| `safety_section` | SAFETY.md section when the check has one, else `null` |
| `severity` | `CRITICAL`, `HIGH`, `MODERATE`, `LOW` or `UNKNOWN` |
| `medications` | Medication strings involved, as supplied |
| `rationale` | The checker's own advisory text, verbatim |
| `details` | Remaining checker fields (matched agents, thresholds, …) |

Findings are sorted by severity, then category and `check_id`. Screens also report
`finding_count`, `severity_counts`, `highest_severity`, `escalation_recommended` (true when any
finding is `HIGH` or `CRITICAL`), `network_used: false`, a `coverage_note` and the `disclaimer`.

### `screen_medications`

| Argument | Type | Notes |
| --- | --- | --- |
| `medications` | array (1–50) of string or `{name, dosage?, route?, frequency?, rxnorm_code?}` | Names may include strength, e.g. `"warfarin 5 mg"` |
| `patient.age` | integer 0–150 | Enables Beers (65+) |
| `patient.pregnant` / `patient.breastfeeding` | boolean | Enable pregnancy / lactation checks |
| `patient.egfr` | number 0–250 (mL/min/1.73m²) | Enables renal dosing |
| `patient.hepatic_function` | `normal` \| `mild` \| `moderate` \| `severe` | Child-Pugh A/B/C; enables hepatic dosing |
| `patient.allergies` | array of strings | Enables allergy checks |
| `patient_ref` | string | Optional audit-linkage reference; HMAC-hashed, never echoed |
| `include_interactions` | boolean, default `true` | Also run the interaction rules |

`patient` rejects any other property (for example `name`), so direct identifiers cannot be sent
by accident. Example call and (trimmed) result:

```json
{"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {
  "name": "screen_medications",
  "arguments": {
    "medications": ["warfarin 5 mg", "ibuprofen 400 mg", "simvastatin 40 mg", "clarithromycin 500 mg"],
    "patient": {"age": 81, "egfr": 28, "allergies": ["Penicillin"]},
    "patient_ref": "ward-7-bed-12"
  },
  "_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28",
            "io.modelcontextprotocol/clientCapabilities": {}}}}
```

```json
{
  "medications_screened": ["warfarin 5 mg", "ibuprofen 400 mg", "simvastatin 40 mg", "clarithromycin 500 mg"],
  "patient_context_used": {"age": 81, "allergies": ["Penicillin"], "egfr": 28},
  "patient_ref_hash": "2ef4b8ba62e116876a74091d8b3f1c1f8044fadc44d4877614fef878728ebf19",
  "checks_run": ["allergy", "allergy_interclass", "beers_criteria", "renal_dose", "duplicate_therapy",
                 "qt_prolongation", "anticholinergic_burden", "serotonin_syndrome", "black_box_warning",
                 "acei_arb_duplication"],
  "checks_skipped": [{"check_id": "pregnancy", "missing": ["pregnant"]},
                     {"check_id": "lactation", "missing": ["breastfeeding"]},
                     {"check_id": "hepatic_dose", "missing": ["hepatic_function"]}],
  "interaction_rules_evaluated": 83,
  "findings": [
    {"check_id": "statin_cyp3a4", "checker": "StatinCyp3a4Checker", "category": "interaction",
     "safety_section": null, "severity": "CRITICAL",
     "medications": ["simvastatin 40 mg", "clarithromycin 500 mg"],
     "rationale": "RESEARCH USE ONLY: Medication 'simvastatin 40 mg' contains simvastatin, ...",
     "details": {"medication": "simvastatin 40 mg", "agent": "simvastatin",
                 "partner_medication": "clarithromycin 500 mg", "partner_agent": "clarithromycin"}}
  ],
  "finding_count": 8,
  "severity_counts": {"CRITICAL": 2, "HIGH": 4, "MODERATE": 2, "LOW": 0, "UNKNOWN": 0},
  "highest_severity": "CRITICAL",
  "escalation_recommended": true,
  "network_used": false,
  "coverage_note": "Deterministic, offline rule set: absence of a finding is NOT evidence of safety. ...",
  "disclaimer": "⚠️  RESEARCH USE ONLY. This output is generated by an AI system ..."
}
```

### `check_drug_interactions`

Argument: `medications`, 2–50 items in the same shapes as above. Output: `medications_checked`,
`rules_evaluated`, findings and the shared summary fields. Real call (modern era):

```json
{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
  "name": "check_drug_interactions",
  "arguments": {"medications": ["warfarin 5 mg", "fluconazole 150 mg"]},
  "_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28",
            "io.modelcontextprotocol/clientCapabilities": {}}}}
```

```json
{"jsonrpc": "2.0", "id": 3, "result": {
  "resultType": "complete",
  "content": [
    {"type": "text", "text": "medagent check_drug_interactions: 1 finding(s) for 2 medication(s); highest severity CRITICAL (escalation recommended).\n[CRITICAL] warfarin_azole (warfarin 5 mg, fluconazole 150 mg): RESEARCH USE ONLY: ...\n⚠️  RESEARCH USE ONLY. ..."},
    {"type": "text", "text": "{\"medications_checked\": [\"warfarin 5 mg\", \"fluconazole 150 mg\"], ...}"}
  ],
  "structuredContent": {
    "medications_checked": ["warfarin 5 mg", "fluconazole 150 mg"],
    "rules_evaluated": 83,
    "findings": [{"check_id": "warfarin_azole", "checker": "WarfarinAzoleChecker", "category": "interaction",
                  "safety_section": null, "severity": "CRITICAL",
                  "medications": ["warfarin 5 mg", "fluconazole 150 mg"],
                  "rationale": "RESEARCH USE ONLY: ... Promptly review therapy and arrange closer INR monitoring with a qualified clinician; do not change therapy from this research output.",
                  "details": {"medication": "warfarin 5 mg", "agent": "warfarin",
                              "partner_medication": "fluconazole 150 mg", "partner_agent": "fluconazole"}}],
    "finding_count": 1, "highest_severity": "CRITICAL", "escalation_recommended": true,
    "network_used": false, "...": "..."
  },
  "isError": false,
  "_meta": {"io.modelcontextprotocol/serverInfo": {"name": "medagent-core", "title": "medagent-core clinical safety tools", "version": "0.1.0"}}
}}
```

The HTTP endpoint `POST /drug-interactions` is a different, network-backed path (RxNorm + OpenFDA
with dual-source validation, SAFETY.md §3.7). The MCP tool never touches the network.

### `parse_fhir_bundle`

Argument: `bundle`, a FHIR R4 `Bundle` (up to 5,000 entries). Uses the existing
`extraction.fhir_parser` for patient context and `FhirMedicationRequestAdapter` for medications,
which drops `stopped`, `cancelled` and `entered-in-error` requests. Result for
[`data/sample_fhir_bundle_polypharmacy.json`](../../data/sample_fhir_bundle_polypharmacy.json)
(synthetic data, trimmed):

```json
{
  "patient_id_hash": "f60ae88463f37fa1469949e53aa60a16db7e157582150fa9fc823fe401f97891",
  "age": 81,
  "sex": "female",
  "chief_complaint": "Atrial fibrillation with new knee pain",
  "diagnoses": ["Atrial fibrillation with new knee pain", "Osteoarthritis of knee"],
  "medications": [{"name": "Warfarin 5 mg tablet", "dosage": "5 mg once daily", "frequency": "daily"},
                  {"name": "Ibuprofen 400 mg tablet", "dosage": "400 mg three times daily"},
                  {"name": "Simvastatin 40 mg tablet"}, {"name": "Clarithromycin 500 mg tablet"}],
  "medication_notes": ["entry[4]: skipped stopped MedicationRequest"],
  "allergies": ["Penicillin"],
  "lab_results": [{"test_name": "eGFR", "value": "28", "unit": "mL/min/1.73m2", "reference_range": null, "abnormal": false},
                  {"test_name": "INR", "value": "3.4", "unit": null, "reference_range": null, "abnormal": false}],
  "vital_signs": [],
  "resource_counts": {"AllergyIntolerance": 1, "Condition": 2, "MedicationRequest": 5, "Observation": 2, "Patient": 1},
  "screening_input": {
    "medications": ["...the four active medications above..."],
    "patient": {"age": 81, "allergies": ["Penicillin"], "egfr": 28.0}
  },
  "notes": ["Direct identifiers (name, birthDate, identifier, telecom, address) and the raw bundle are not returned; the patient id is HMAC-SHA256 hashed with PII_HASH_SALT.",
            "Medications exclude stopped, cancelled and entered-in-error requests.",
            "pregnant, breastfeeding and hepatic_function are not derived from the bundle; add them to screening_input.patient when known.",
            "egfr is the lowest of 1 numeric eGFR observation(s)."],
  "disclaimer": "⚠️  RESEARCH USE ONLY. ..."
}
```

Pass `screening_input` unchanged as the `arguments` of `screen_medications`. Chief complaint and
diagnosis text are passed through `sanitise_clinical_text` (dates, phone numbers, emails, MRNs and
SSNs are redacted). When several eGFR observations exist, the **lowest** numeric value is used —
the conservative choice for renal screening.

### `list_safety_controls`

Arguments: optional `category` (`platform`, `patient_context`, `medication_list`, `interaction`)
and `query` (case-insensitive substring over id, title, description and checker). With no
arguments it returns 104 entries today (8 platform constraints, 7 patient-context checks, 6
medication-list checks, 83 interaction rules):

```json
{"count": 6,
 "counts_by_category": {"platform": 0, "patient_context": 0, "medication_list": 0, "interaction": 6},
 "controls": [{"id": "amio_warfarin", "title": "Flag amiodarone co-prescribed with warfarin (INR potentiation)",
               "safety_section": null, "description": "Flag amiodarone co-prescribed with warfarin (INR potentiation)",
               "category": "interaction", "kind": "deterministic_checker",
               "checker": "AmioWarfarinChecker", "requires": []}, "..."],
 "disclaimer": "⚠️  RESEARCH USE ONLY. ..."}
```

(`{"query": "warfarin"}` shown.)

## Protocol and dual-era compatibility

| Client | How it opens | Server behaviour | Result shape |
| --- | --- | --- | --- |
| Modern (2026-07-28) | Any request carrying `_meta["io.modelcontextprotocol/protocolVersion"] = "2026-07-28"` and `_meta["io.modelcontextprotocol/clientCapabilities"]` | Served statelessly, request by request | `resultType: "complete"` and `_meta["io.modelcontextprotocol/serverInfo"]` on every result; `tools/list` adds `ttlMs: 3600000`, `cacheScope: "public"` |
| Dual-era (e.g. Inspector `--protocol-era auto`) | `server/discover` probe | Returns a `DiscoverResult`, so the client stays modern | Modern |
| Legacy 2025-11-25 / 2025-06-18 | `initialize` | Echoes the requested version and serves the stdio process with legacy semantics; modern requests are still accepted on the same process | Legacy (no `resultType`; `serverInfo` in the `initialize` result) |
| Legacy with an unknown version (e.g. 2024-11-05) | `initialize` | Offers `2025-11-25` | Legacy |
| Modern client on an unsupported version | Any request | `-32022 Unsupported protocol version`, `data: {"supported": [...], "requested": "..."}` | Error |
| No `_meta` version and no prior `initialize` | Any request | `-32602` naming the missing `_meta` field and the `initialize` alternative | Error |

`server/discover` (modern):

```json
{"jsonrpc": "2.0", "id": 1, "result": {
  "resultType": "complete",
  "supportedVersions": ["2026-07-28", "2025-11-25", "2025-06-18"],
  "capabilities": {"tools": {}},
  "instructions": "medagent-core exposes deterministic, offline medication-safety tools for RESEARCH USE ONLY. ...",
  "ttlMs": 3600000,
  "cacheScope": "public",
  "_meta": {"io.modelcontextprotocol/serverInfo": {"name": "medagent-core", "title": "medagent-core clinical safety tools", "version": "0.1.0"}}
}}
```

`initialize` (legacy, requesting 2025-06-18):

```json
{"jsonrpc": "2.0", "id": 9, "result": {
  "protocolVersion": "2025-06-18",
  "capabilities": {"tools": {"listChanged": false}},
  "serverInfo": {"name": "medagent-core", "title": "medagent-core clinical safety tools", "version": "0.1.0"},
  "instructions": "..."
}}
```

### Errors

| Code | When |
| --- | --- |
| `-32700` | Line is not valid JSON (the response has no `id`) |
| `-32600` | Batch array, non-object message, `jsonrpc` ≠ `"2.0"`, missing/non-string `method`, `null`/boolean id, non-object `params`, message over 8 MiB |
| `-32601` | Method outside the era's surface: `initialize`/`ping` on 2026-07-28 requests, `resources/*`, `prompts/*`, `logging/setLevel`, … |
| `-32602` | Missing required `_meta` fields, unknown tool, malformed `tools/call`, any `tools/list` cursor (not paginated) |
| `-32603` | Unexpected server error (details only on stderr) |
| `-32022` | Unsupported protocol version |

Argument problems are **tool errors**, not protocol errors, so the model can correct itself:

```json
{"resultType": "complete", "isError": true, "content": [{"type": "text",
  "text": "Invalid arguments: arguments.medications must contain at least 1 item(s); arguments.patient.name is not an allowed property\n⚠️  RESEARCH USE ONLY. ..."}]}
```

Notifications (`notifications/initialized`, `notifications/cancelled`, unknown ones) never get a
response. The server exits promptly when stdin is closed.

## Safety model

- **Deterministic and offline.** Tools only call existing medagent checkers, the FHIR parser and
  the MedicationRequest adapter: no LLM, no network, no state between requests.
- **Mandatory disclaimer everywhere.** `MANDATORY_DISCLAIMER` (SAFETY.md §3.1) is in every
  `structuredContent` and every text block, including tool errors.
- **No prescribing directives.** Rationales are the checkers' advisory text. Before a result
  leaves the server, its summary and structured content are screened with the same
  prohibited-prescription patterns as LLM output (SAFETY.md §3.3); a match withholds the result as
  an `isError` tool result and logs `mcp_output_withheld`.
- **Escalation, not reassurance.** `escalation_recommended` is set for any `HIGH`/`CRITICAL`
  finding, skipped checks are listed, and every result says that an empty result is not evidence
  of safety.
- **De-identification.** `patient` accepts no identifier fields; `patient_ref` and FHIR patient ids
  are HMAC-SHA256 hashed with `PII_HASH_SALT` (`safety/pii_hasher.py`) and never echoed; FHIR names,
  birth dates, identifiers, telecom, addresses and the raw bundle are never returned; free text is
  passed through `sanitise_clinical_text`.
- **Scope enforcement.** Free-text arguments (medication strings, allergies, catalogue queries) go
  through `ScopeEnforcer` (SAFETY.md §3.6); a violation is a tool error.
- **Audit trail.** With `--audit-log`, each `tools/call` appends one JSON line holding hashes and
  counts only — never arguments or results.
- **Protocol hygiene.** STDOUT carries JSON-RPC only: logs go to STDERR (default level `WARNING`),
  and `sys.stdout` is redirected to STDERR inside the server so a stray `print` cannot corrupt the
  stream. Inputs are bounded (50 medications, 50 allergies, 5,000 FHIR entries, 8 MiB per message).
- **Human in the loop.** Keep your host's tool-approval prompts on, and route every finding to a
  licensed clinician.

> ⚠️  RESEARCH USE ONLY. This output is generated by an AI system and has NOT been reviewed by a
> licensed clinician. It is NOT FDA-cleared and MUST NOT be used to guide clinical treatment
> decisions. Always consult a qualified healthcare professional for medical advice, diagnosis, or
> treatment.

## Configuration

| Setting | Flag | Environment | Default |
| --- | --- | --- | --- |
| JSONL audit file | `--audit-log PATH` | `MEDAGENT_MCP_AUDIT_LOG` | off |
| STDERR log level | `--log-level LEVEL` | `MEDAGENT_MCP_LOG_LEVEL` | `WARNING` |
| Identifier hashing key | — | `PII_HASH_SALT` | insecure default (warned) |

An audit record (real output, `screen_medications` with `patient_ref`):

```json
{"client": {"name": "docs", "version": "1.0"}, "duration_ms": 9.26, "era": "modern", "error_kind": null,
 "event": "mcp_tool_call", "finding_count": 4, "highest_severity": "HIGH",
 "inputs_hash": "c3d1601a0d5f573940009c73d0749deaa7d6f57a2d8665df6115a7a0d6d85270", "is_error": false,
 "patient_id_hash": null, "patient_ref_hash": "2ef4b8ba62e116876a74091d8b3f1c1f8044fadc44d4877614fef878728ebf19",
 "protocol_version": "2026-07-28", "timestamp": "2026-11-07T07:12:17.897+00:00", "tool": "screen_medications"}
```

`inputs_hash` is an HMAC of the canonical arguments, so identical calls can be linked without
storing them. `error_kind` is `invalid_arguments` or `output_withheld` for tool errors. A failed
audit write is logged (`mcp_audit_write_failed`) and never breaks the tool call.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `Missing required _meta field 'io.modelcontextprotocol/protocolVersion'` | The client sent a request without per-request metadata and without `initialize`. Legacy clients must call `initialize` first; modern clients must send `_meta` on every request. |
| `-32022 Unsupported protocol version` | Retry with a version from `error.data.supported`, or upgrade the client/server. |
| Host shows the server as failed or "spawn ENOENT" | Use the absolute path to `medagent-mcp` inside your virtualenv. Claude Desktop writes server stderr to its MCP logs (`~/Library/Logs/Claude/mcp*.log` on macOS). |
| Client reports invalid JSON from the server | Something else wrote to stdout. Launch `medagent-mcp` directly, not through a wrapper that prints. |
| `pii_hash_salt_default` warning on stderr | Set `PII_HASH_SALT` to a long random secret in the host's `env` block. |
| `isError: true` with `Invalid arguments: …` | Fix the argument at the reported path (for example `arguments.patient.egfr must be <= 250`). |
| `Input rejected by scope enforcement` | A free-text argument asked for browsing, code execution or a non-clinical task. |
| Fewer checks than expected | Look at `checks_skipped`; supply `age`, `egfr`, `hepatic_function`, `pregnant`, `breastfeeding` or `allergies`. |
| Large bundle rejected (`Message exceeds 8388608 bytes`) | Split the bundle, or send only the Patient, MedicationRequest, Observation and AllergyIntolerance entries. |
| Gemini/OpenAPI clients reject a schema | Not expected: `tools/list --strict` in the MCP Inspector reports 0 errors and 0 warnings. Please open an issue with the client name. |

## Limitations

- Medication matching is name-based and deterministic (whole-token, plus aliases defined by each
  checker); there is no RxNorm normalisation, and coverage is limited to the curated rules.
- No dose calculations, no indication checks, no lab-trend bridges or scorers over MCP.
- Pregnancy, lactation and hepatic status are never inferred from FHIR.
- stdio transport only (no Streamable HTTP); tools only (no resources or prompts).

## How this demo was recorded

The GIF is rendered from a real stdio session. Every `$` line in
[`mcp_server_demo_transcript.txt`](mcp_server_demo_transcript.txt) was executed verbatim and
the transcript holds its unedited output (macOS, Python 3.12, MCP Inspector 2.14.0, 2026-11-06):

```bash
uv venv .venv-mcp-demo && uv pip install --python .venv-mcp-demo/bin/python -e .
export PATH="$PWD/.venv-mcp-demo/bin:$PATH"
medagent-mcp --version
PII_HASH_SALT=demo-only-salt python scripts/mcp_stdio_demo.py
npx @modelcontextprotocol/inspector@2.14.0 --cli medagent-mcp --protocol-era auto --method initialize --format json -q 2>/dev/null | jq -r .result.protocolVersion
npx @modelcontextprotocol/inspector@2.14.0 --cli medagent-mcp --protocol-era legacy --method initialize --format json -q 2>/dev/null | jq -r .result.protocolVersion
```

Render the transcript (Pillow, typing animation for `$` lines), then share one 16-colour palette
across frames with ffmpeg to keep the file under 300 KB:

```bash
uv run --with pillow python scripts/render_transcript_gif.py \
  --input docs/guides/mcp_server_demo_transcript.txt --output mcp_raw.gif \
  --title "medagent-core: dual-era MCP server (stdio)" --rows 42 --type-steps 4
ffmpeg -i mcp_raw.gif -filter_complex \
  "[0:v]split[a][b];[a]palettegen=max_colors=16:stats_mode=full[p];[b][p]paletteuse=dither=none:diff_mode=rectangle" \
  assets/mcp_server_demo.gif && rm mcp_raw.gif
```

## See also

- [SAFETY.md §9](../../SAFETY.md#9-mcp-server-model-context-protocol-safety-model) — MCP safety model
- [ARCHITECTURE.md](../../ARCHITECTURE.md#mcp-server) — where the server sits
- Spec: [MCP 2026-07-28 versioning](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning),
  [`server/discover`](https://modelcontextprotocol.io/specification/2026-07-28/server/discover),
  [stdio transport](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio),
  [tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
