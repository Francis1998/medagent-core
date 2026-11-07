# Use cases — three end-to-end scenarios

> **⚠️ RESEARCH USE ONLY — NOT FDA-cleared — NOT for clinical deployment.** Every scenario below
> produces research output for a licensed clinician to review; nothing here is a treatment order.

Each scenario uses commands that ship with this repository. The outputs were captured from real
runs on 2026-11-07 and are abridged only where marked. Scenarios 1 and 3 run fully offline with no
API keys. Scenario 2 shows the HTTP API's fail-safe path without keys, and its normal path when a
key is configured.

| # | Scenario | Interface | Needs |
|---|---|---|---|
| 1 | [Polypharmacy safety review from an EHR export](#1-polypharmacy-safety-review-from-an-ehr-export) | MCP (`medagent-mcp`) | nothing (offline) |
| 2 | [Auditable reasoning that fails safe](#2-auditable-reasoning-that-fails-safe) | HTTP (`/analyze`) + audit log | optional LLM key |
| 3 | [Safety-control inventory for a research protocol](#3-safety-control-inventory-for-a-research-protocol) | MCP + test suite | nothing (offline) |

Setup for all three:

```bash
git clone https://github.com/Francis1998/medagent-core && cd medagent-core
pip install -e ".[dev]"
export PII_HASH_SALT=change-me        # identifiers are HMAC-hashed with this salt
```

---

## 1. Polypharmacy safety review from an EHR export

**Who:** a pharmacy-informatics researcher with a FHIR R4 export of an older patient's record who
wants medagent's MCP-exposed deterministic checks run on it (13 patient-context and medication-list
checks plus 83 interaction rules). Steps 1 and 2 send nothing to a model provider.

**Step 1: run the reference MCP client** over real stdio. It parses the synthetic bundle
`data/sample_fhir_bundle_polypharmacy.json` and screens the result:

```bash
python scripts/mcp_stdio_demo.py
```

```text
→ tools/call parse_fhir_bundle   (sample_fhir_bundle_polypharmacy.json)
← patient fa5656dd9864… (hashed) · age 81 · 4 active meds · egfr 28.0 · identifiers echoed: 0
→ tools/call screen_medications   (arguments = screening_input)
← 8 findings · highest CRITICAL · escalation_recommended=True
   CRITICAL statin_cyp3a4      Simvastatin 40 mg + Clarithromycin 500 mg
   CRITICAL statin_macrolide   Simvastatin 40 mg + Clarithromycin 500 mg
   HIGH     renal_dose         Ibuprofen 400 mg
   HIGH     black_box_warning  Warfarin 5 mg
   HIGH     anticoag_bleeding  Warfarin 5 mg + Ibuprofen 400 mg
   HIGH     warfarin_nsaid     Warfarin 5 mg + Ibuprofen 400 mg
   MODERATE black_box_warning  Ibuprofen 400 mg
   MODERATE qt_prolongation    Clarithromycin 500 mg
   not run (missing context): pregnancy, lactation, hepatic_dose
```

(Abridged: the full run also shows `server/discover`, `tools/list` and a legacy-client session.)

**Step 2: check an ad-hoc regimen** with one raw JSON-RPC request (any MCP host sends the same):

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}},"name":"check_drug_interactions","arguments":{"medications":["warfarin 5 mg daily","amiodarone 200 mg daily","clarithromycin 500 mg bid"]}}}' \
  | medagent-mcp \
  | jq -c '.result.structuredContent | {highest_severity, escalation_recommended, network_used, findings: [.findings[] | {check_id, severity, medications}]}'
```

```json
{"highest_severity":"CRITICAL","escalation_recommended":true,"network_used":false,"findings":[{"check_id":"qtc_ddi","severity":"CRITICAL","medications":["clarithromycin 500 mg bid","amiodarone 200 mg daily"]},{"check_id":"amio_warfarin","severity":"HIGH","medications":["amiodarone 200 mg daily","warfarin 5 mg daily"]}]}
```

**Step 3: use it from an assistant.** Register the server with Claude Code (other hosts are covered
in the [MCP server guide](MCP_SERVER_GUIDE.md#connect-a-client)) and ask, for example, *"Parse this
FHIR bundle and screen the medications"*. Use synthetic or already de-identified data here: a hosted
assistant's model sees whatever you paste or attach before medagent's tools de-identify anything,
and `network_used: false` describes medagent's tools only. Keep raw EHR exports in a local client,
as in steps 1 and 2.

```bash
claude mcp add --env PII_HASH_SALT=change-me --transport stdio medagent -- "$(which medagent-mcp)"
```

**What this demonstrates:**
- Deterministic, offline screening (`network_used: false`).
- De-identification: the patient id is hashed, and `identifiers echoed: 0`.
- Explicit gaps: checks that lack context are listed as "not run" rather than silently passed.
- The mandatory disclaimer on every result.

---

## 2. Auditable reasoning that fails safe

**Who:** a health-AI team evaluating whether the agent refuses to guess when it cannot reason. It
must leave an audit trail either way.

**Step 1: start the API in one terminal.** To see the fail-safe path, leave every `*_API_KEY`
unset. Knowledge retrieval still queries PubMed, RxNorm and OpenFDA when the network is available.

```bash
uvicorn medagent.api.main:app --port 8000    # terminal 1: keeps running in the foreground
```

Run the remaining commands in a **second terminal**:

```bash
curl -s localhost:8000/health
```

```json
{"status":"ok","agent_ready":true,"version":"0.1.0","timestamp":"2026-11-07T08:53:48.089408"}
```

**Step 2: ask for a differential** (the STEMI case from [QUICKSTART.md](../../QUICKSTART.md)).
`/analyze` does not de-identify its input: the caller supplies the hashed `patient_id_hash`, and
free text must not contain identifiers.

```bash
curl -s -X POST localhost:8000/analyze -H 'Content-Type: application/json' -d '{
  "patient_context": {
    "patient_id_hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
    "age": 65, "sex": "male",
    "chief_complaint": "Chest pain radiating to left arm, diaphoresis",
    "clinical_notes": "2-hour history of crushing substernal chest pain radiating to left arm. ECG shows ST elevation in V1-V4.",
    "diagnoses_history": ["Essential hypertension"],
    "medications": [{"name": "aspirin", "dosage": "81mg", "route": "oral"},
                    {"name": "metoprolol", "dosage": "25mg", "route": "oral"}],
    "lab_results": [{"test_name": "Troponin I", "value": "2.4", "unit": "ng/mL", "abnormal": true}]
  },
  "query": "What is the differential diagnosis for this presentation?"
}' | jq -c '.result | {state_reached, escalated, overall_confidence, uncertainty_flags}'
```

Without an LLM key, no hypothesis can be generated, so the state machine escalates instead of
answering:

```json
{"state_reached":"ESCALATE","escalated":true,"overall_confidence":0.0,"uncertainty_flags":["No hypotheses generated — human review required"]}
```

**Step 3: inspect the durable audit record** written for the run (`DATABASE_URL` defaults to
`data/audit.db`):

```bash
sqlite3 -header -column data/audit.db \
  "select session_id, state_reached, escalated, overall_confidence from audit_log order by id desc limit 1"
```

```text
session_id                            state_reached  escalated  overall_confidence
------------------------------------  -------------  ---------  ------------------
d0f298af-4959-40fc-be9a-5ca4159a3c0e  ESCALATE       1          0.0
```

**With a key:** set any `*_API_KEY` in `.env` (see [CONFIGURATION.md](../../CONFIGURATION.md) for
the current default models). Restart the API, because settings and provider keys are read at
startup, then repeat step 2. The response then carries ranked hypotheses, an
evidence chain and the mandatory disclaimer. It reaches `OUTPUT` only when overall confidence is at
least 0.6 and the evidence is not contradictory; otherwise it escalates.

**What this demonstrates:**
- The explicit state machine never fabricates an answer: `ESCALATE` is a first-class outcome.
- Every completed run, escalated or not, is persisted to the audit log, keyed by session.

---

## 3. Safety-control inventory for a research protocol

**Who:** an investigator preparing an IRB/ethics submission or a model-risk review who must state
which safeguards are enforced in code and show the tests that prove them.

**Step 1: list the platform controls** and the SAFETY.md section that documents each:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}},"name":"list_safety_controls","arguments":{"category":"platform"}}}' \
  | medagent-mcp | jq -r '.result.structuredContent.controls[] | "\(.id)\t§\(.safety_section)\t\(.title)"'
```

```text
mandatory_disclaimer	§3.1	Mandatory research-use disclaimer
system_prompt_constraints	§3.2	Immutable system prompt constraints
medical_output_validation	§3.3	Prohibited prescription-language validation
escalate_state	§3.4	ESCALATE on low confidence or contradictory evidence
pii_deidentification	§3.5	PII de-identification
scope_enforcement	§3.6	Scope enforcement
drug_interaction_dual_source	§3.7	Drug-interaction dual-source validation (HTTP API)
hard_timeouts	§3.8	Hard timeouts
```

**Step 2: see what the catalog covers** (omit `category` to list all entries):

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}},"name":"list_safety_controls","arguments":{}}}' \
  | medagent-mcp | jq -c '.result.structuredContent | {count, counts_by_category}'
```

```json
{"count":104,"counts_by_category":{"platform":8,"patient_context":7,"medication_list":6,"interaction":83}}
```

The 104 entries are a catalog, not 104 offline checks. The 8 `platform` entries are documented
constraints of the agent, and some run only on the HTTP path: dual-source drug validation, for
example, queries RxNorm and OpenFDA. The other 96 are the deterministic checks that run offline over
MCP: 7 patient-context and 6 medication-list screening checks plus 83 interaction rules.

**Step 3: attach the evidence.** Run the suites that enforce these controls and cite the
corresponding [SAFETY.md](../../SAFETY.md) sections. The suites cover:
- the MCP tools and safety library: `tests/unit/mcp`, `tests/unit/safety`;
- the ESCALATE gate and audit log: `tests/unit/agent`;
- dual-source drug validation: `tests/unit/retrieval`.

```bash
pytest tests/unit/mcp tests/unit/safety tests/unit/agent tests/unit/retrieval -q
```

```text
2036 passed, 17 warnings in 1.86s
```

**What this demonstrates:**
- Safety claims are traceable from control → documentation section → code → passing tests.
- Each per-panel entry (summary and demo GIF) is listed in the
  [safety panel catalog](../SAFETY_PANEL_CATALOG.md).

---

## Also useful: a simulated walkthrough for stakeholders

`python scripts/demo.py --case all --no-delay` replays three **pre-canned** cases in the terminal:
an MI differential (`OUTPUT`, 0.81), a drug-interaction case (`OUTPUT`, 0.72) and an ambiguous
presentation (`ESCALATE`, 0.38 with contradictory evidence). It is a scripted simulation for
explaining the state machine and makes no model or network calls, so use scenarios 1–3 for real
results.
