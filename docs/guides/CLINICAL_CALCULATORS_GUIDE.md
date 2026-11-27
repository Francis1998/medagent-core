# Clinical Calculators Guide

![Clinical calculators over HTTP and MCP](../../assets/clinical_calculators_demo.gif)

> **RESEARCH USE ONLY.** The calculators are deterministic research tools. They are not a
> substitute for clinical judgement, they are not FDA-cleared, every input must be verified
> by a qualified clinician, and no result is a treatment recommendation.

medagent ships a typed registry of **13 audited clinical calculators** — CURB-65,
CHA2DS2-VASc, HAS-BLED, HEART, Wells PE, PERC, qSOFA, NEWS2, MELD-Na, Child-Pugh, the
Glasgow Coma Scale, Centor (McIsaac) and the race-free CKD-EPI 2021 creatinine eGFR —
exposed as tools: `GET /calculators`, `GET /calculators/{id}` and `POST /calculators/{id}`
over HTTP, and the read-only MCP tools `list_calculators` and `run_calculator`. Each
calculator takes **raw patient values with units** (urea in mmol/L or BUN in mg/dL,
creatinine and bilirubin in mg/dL or µmol/L, albumin in g/dL or g/L, temperature in °C or
°F), derives every criterion transparently and returns the score, the points each
criterion contributed with the rule that fired, the published interpretation band, the
citation (DOI/PMID), limitations and the mandatory disclaimer. An LLM agent calls tested
code instead of doing clinical arithmetic itself.

The demo above is a real run of [`scripts/clinical_calculators_demo.sh`](../../scripts/clinical_calculators_demo.sh);
its transcript is [`clinical_calculators_demo_transcript.txt`](clinical_calculators_demo_transcript.txt).

## Contents

- [Why: the gap and how popular projects solve it](#why-the-gap-and-how-popular-projects-solve-it)
- [Prerequisites](#prerequisites)
- [Quickstart](#quickstart)
- [Calculator catalogue](#calculator-catalogue)
- [Inputs, units and validation](#inputs-units-and-validation)
- [HTTP API reference](#http-api-reference)
- [MCP reference](#mcp-reference)
- [Result reference](#result-reference)
- [How an LLM agent should call the calculators](#how-an-llm-agent-should-call-the-calculators)
- [Worked examples](#worked-examples)
- [Audit results](#audit-results)
- [Configuration](#configuration)
- [How it fits with the rest of medagent](#how-it-fits-with-the-rest-of-medagent)
- [Safety and limitations](#safety-and-limitations)
- [Limitations and roadmap](#limitations-and-roadmap)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

## Why: the gap and how popular projects solve it

[MedCalc-Bench](https://github.com/ncbi-nlp/MedCalc-Bench) (Khandekar et al., NeurIPS 2024
Datasets & Benchmarks) showed that frontier LLMs are unreliable at medical calculation —
they misapply cut-offs, skip unit conversions and slip on arithmetic — and that handing the
arithmetic to deterministic code fixes most of it. Clinicians use
[MDCalc](https://www.mdcalc.com/) for the same reason, and MCP calculator servers expose
calculators to agents as tools.

| Project | How calculators are exposed | Units | Transparency | Evidence |
| --- | --- | --- | --- | --- |
| [MedCalc-Bench](https://github.com/ncbi-nlp/MedCalc-Bench) | 55 Python reference implementations plus a benchmark of patient notes | Converters (`unit_converter_new.py`) | Step-by-step ground-truth explanations | Benchmark answers |
| [MDCalc](https://www.mdcalc.com/) | Web calculators with criteria pages | US / SI toggle | Points per criterion | Evidence and references per calculator |
| [winninghealth/medcalcmcp](https://github.com/winninghealth/medcalcmcp) | FastMCP server: `list_calculators(category)`, `get_calculator_info(id)`, `calculate(id, parameters)` with integer ids | Per calculator | Result and interpretation | Ported from MedCalc-Bench |
| medagent before this feature | 87 `*_scorer.py` modules in `src/medagent/safety/`, unreachable from the API, CDS Hooks or MCP; inputs were pre-thresholded booleans (`Curb65Factors.urea_over_7`), so the caller applied cut-offs and conversions | None | Factor names only | None |
| **medagent now** | `GET/POST /calculators` and MCP `list_calculators` / `run_calculator` (both protocol eras) over one typed registry | Canonical unit plus accepted alternatives with conversions and physiological ranges | Every criterion with its points and the rule that fired | Audited against the original publications and MedCalc-Bench; DOI/PMID; limitations |

What medagent adds over the references: stable string ids with a version, explicit units
on every quantity (a bare number is rejected where it would be ambiguous), validation that
never treats a missing criterion as "absent", the derivation of each criterion in the
result, wrapped and audited existing scorers (four scorer bugs were fixed on the way — see
[Audit results](#audit-results)), and medagent's safety posture: mandatory disclaimer,
prescription-language output guard and logs that carry the calculator id and outcome band
only.

## Prerequisites

- medagent installed (`pip install -e ".[dev]"`, see [QUICKSTART](../../QUICKSTART.md)).
- Nothing else: the calculators are offline and deterministic, need no LLM key, no
  network and no database, and add no settings.
- For the demo script: `curl` and `jq`.

## Quickstart

Python:

```python
from medagent.calculators import run_calculator

result = run_calculator(
    "curb_65",
    {
        "confusion": False,
        "urea": {"value": 26, "unit": "mg/dL"},  # BUN, converted to urea mmol/L
        "respiratory_rate": 31,
        "systolic_bp": 118,
        "diastolic_bp": 72,
        "age": 72,
    },
)
print(result["score"], result["interpretation"]["band"])  # 3 severe
for component in result["components"]:
    print(component["points"], component["rule"])
```

HTTP (start the API with `PII_HASH_SALT=demo-only-salt medagent --port 8000`):

```bash
curl -s localhost:8000/calculators | jq -r '.calculators[].id'
curl -s localhost:8000/calculators/curb_65 | jq '.inputs[] | {name, unit, accepted_units}'
curl -s -X POST localhost:8000/calculators/curb_65 -H 'Content-Type: application/json' \
  -d '{"inputs": {"confusion": false, "urea": {"value": 26, "unit": "mg/dL"},
       "respiratory_rate": 31, "systolic_bp": 118, "diastolic_bp": 72, "age": 72}}' \
  | jq '{score, interpretation, components: [.components[].rule]}'
```

MCP (stdio; configure `python -m medagent.mcp` in your client as in the
[MCP server guide](MCP_SERVER_GUIDE.md)):

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"run_calculator",
  "arguments":{"calculator_id":"gcs","inputs":{"eye":3,"verbal":4,"motor":6}},
  "_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28",
  "io.modelcontextprotocol/clientCapabilities":{}}}}' | tr -d '\n' | python -m medagent.mcp
```

## Calculator catalogue

All ids, inputs and bands below are generated from the registry (`medagent.calculators.CALCULATORS`).
Inputs are required unless marked optional; `GET /calculators/{id}` returns each input's
description, range and conversion. Bands describe risk strata from the cited publications.

| Id | Calculator | Inputs (units) | Score | Bands | Source |
| --- | --- | --- | --- | --- | --- |
| `centor_mcisaac` | Centor score, McIsaac modification (streptococcal pharyngitis) | `age` years, `temperature` °C or °F, `cough_absent` bool, `tender_anterior_cervical_nodes` bool, `tonsillar_swelling_or_exudate` bool | -1 to 5 | -1 to 1 `low`; 2-3 `moderate`; 4-5 `high` | [PMID 9475915](https://pubmed.ncbi.nlm.nih.gov/9475915/); [doi:10.1001/jama.291.13.1587](https://doi.org/10.1001/jama.291.13.1587) |
| `cha2ds2_vasc` | CHA2DS2-VASc (stroke risk in atrial fibrillation) | `age` years, `sex` female/male, `congestive_heart_failure` bool, `hypertension` bool, `diabetes` bool, `stroke_tia_thromboembolism` bool, `vascular_disease` bool | 0-9 | 0 `low`; 1 `moderate`; 2-9 `high` | [doi:10.1378/chest.09-1584](https://doi.org/10.1378/chest.09-1584) |
| `child_pugh` | Child-Pugh score (cirrhosis severity) | `bilirubin` mg/dL or µmol/L, `albumin` g/dL or g/L, `inr` number, `ascites` none/slight/moderate_to_severe, `encephalopathy` none/grade_1_2/grade_3_4 | 5-15 | 5-6 `class_a`; 7-9 `class_b`; 10-15 `class_c` | [doi:10.1002/bjs.1800600817](https://doi.org/10.1002/bjs.1800600817) |
| `ckd_epi_2021` | CKD-EPI 2021 creatinine eGFR (race-free) | `creatinine` mg/dL or µmol/L, `age` years, `sex` female/male | > 0 mL/min/1.73 m2 | >= 90 `g1`; 60-89 `g2`; 45-59 `g3a`; 30-44 `g3b`; 15-29 `g4`; < 15 `g5` | [doi:10.1056/NEJMoa2102953](https://doi.org/10.1056/NEJMoa2102953); [KDIGO 2012](https://kdigo.org/guidelines/ckd-evaluation-and-management/) |
| `curb_65` | CURB-65 (community-acquired pneumonia severity) | `confusion` bool, `urea` mmol/L or mg/dL, `respiratory_rate` breaths/min, `systolic_bp` mmHg, `diastolic_bp` mmHg, `age` years | 0-5 | 0-1 `mild`; 2 `moderate`; 3-5 `severe` | [doi:10.1136/thorax.58.5.377](https://doi.org/10.1136/thorax.58.5.377) |
| `gcs` | Glasgow Coma Scale | `eye` integer, `verbal` integer, `motor` integer | 3-15 | 3-8 `severe`; 9-12 `moderate`; 13-15 `mild` | [doi:10.1016/S0140-6736(74)91639-0](https://doi.org/10.1016/S0140-6736(74)91639-0) |
| `has_bled` | HAS-BLED (major bleeding risk on anticoagulation) | `age` years, `uncontrolled_hypertension` bool, `abnormal_renal_function` bool, `abnormal_liver_function` bool, `stroke_history` bool, `bleeding_history` bool, `labile_inr` bool, `antiplatelet_or_nsaid` bool, `alcohol_excess` bool | 0-9 | 0-1 `low`; 2 `moderate`; 3-9 `high` | [doi:10.1378/chest.10-0134](https://doi.org/10.1378/chest.10-0134) |
| `heart` | HEART score for major adverse cardiac events | `history` slightly_suspicious/moderately_suspicious/highly_suspicious, `ecg` normal/nonspecific_repolarization/significant_st_deviation, `age` years, `hypercholesterolemia` bool, `hypertension` bool, `diabetes` bool, `smoking` bool, `family_history` bool, `obesity` bool, `atherosclerotic_disease` bool, `troponin` number, `troponin_uln` number | 0-10 | 0-3 `low`; 4-6 `moderate`; 7-10 `high` | [doi:10.1007/BF03086144](https://doi.org/10.1007/BF03086144) |
| `meld_na` | MELD-Na (Model for End-Stage Liver Disease with sodium) | `bilirubin` mg/dL or µmol/L, `inr` number, `creatinine` mg/dL or µmol/L, `sodium` mmol/L or mEq/L, `dialysis` bool | 6-40 | 6-9 `meld_lt_10`; 10-19 `meld_10_19`; 20-29 `meld_20_29`; 30-39 `meld_30_39`; 40 `meld_ge_40` | [doi:10.1056/NEJMoa0801209](https://doi.org/10.1056/NEJMoa0801209); [doi:10.1053/gast.2003.50016](https://doi.org/10.1053/gast.2003.50016) |
| `news2` | NEWS2 (National Early Warning Score 2) | `respiratory_rate` breaths/min, `oxygen_saturation` %, `spo2_scale` scale_1/scale_2 (optional), `supplemental_oxygen` bool, `systolic_bp` mmHg, `heart_rate` beats/min, `consciousness` alert/new_confusion/voice/pain/unresponsive, `temperature` °C or °F | 0-20 | 0-4 `low`; red score `low_medium`; 5-6 `moderate`; 7-20 `high` | [RCP 2017](https://www.rcp.ac.uk/resources/national-early-warning-score-news-2/) |
| `perc` | PERC rule for pulmonary embolism | `age` years, `heart_rate` beats/min, `oxygen_saturation` %, `unilateral_leg_swelling` bool, `hemoptysis` bool, `recent_surgery_or_trauma` bool, `prior_pe_or_dvt` bool, `hormone_use` bool | 0-8 | 0 `perc_negative`; 1-8 `perc_positive` | [doi:10.1111/j.1538-7836.2004.00790.x](https://doi.org/10.1111/j.1538-7836.2004.00790.x) |
| `qsofa` | qSOFA (quick Sequential Organ Failure Assessment) | `respiratory_rate` breaths/min, `systolic_bp` mmHg, `altered_mentation` bool | 0-3 | 0-1 `negative`; 2-3 `positive` | [doi:10.1001/jama.2016.0288](https://doi.org/10.1001/jama.2016.0288) |
| `wells_pe` | Wells criteria for pulmonary embolism | `clinical_dvt_signs` bool, `pe_most_likely_diagnosis` bool, `heart_rate` beats/min, `immobilization_or_recent_surgery` bool, `previous_dvt_or_pe` bool, `hemoptysis` bool, `malignancy` bool | 0-12.5 | < 2 `low`; 2-6 `moderate`; > 6 `high` | [PMID 10744147](https://pubmed.ncbi.nlm.nih.gov/10744147/) |

The point-based calculators wrap the existing scorers in `src/medagent/safety/`
(`Curb65PneumoniaScorer`, `Cha2ds2VascStrokeRiskScorer`, `HasBledBleedRiskScorer`,
`HeartScoreAcsScorer`, `WellsPeProbabilityScorer`, `PercPeExclusionScorer`,
`QSofaSepsisScreenScorer`, `News2EarlyWarningScorer`, `MeldNaScorer`,
`ChildPughLiverSeverityScorer`, `GcsNeurologicStatusScorer`,
`CentorStrepPharyngitisScorer`): the calculator derives each criterion from the raw values,
the scorer produces the total, and the registry checks that both agree. CKD-EPI 2021 is new
(`medagent.calculators.hepatorenal.ckd_epi_2021_egfr`).

## Inputs, units and validation

`inputs` is a JSON object keyed by input name. Every input has a type:

| Type | JSON form | Example |
| --- | --- | --- |
| `boolean` | `true` / `false` (not `0` / `1`) | `"confusion": false` |
| `choice` | one of the listed strings | `"consciousness": "voice"` |
| `integer` | whole number in the canonical unit, or `{"value", "unit"}` | `"age": 72`, `"heart_rate": 112` |
| `number` | number, or `{"value": <number>, "unit": "<unit>"}` | `"inr": 1.8`, `"creatinine": {"value": 168, "unit": "µmol/L"}` |

**Explicit units.** A quantity with an alternative unit that changes the number
(creatinine, bilirubin, albumin, urea, temperature) must be sent as
`{"value": <number>, "unit": "<unit>"}`; a bare number is rejected because 1.3 could be
mg/dL or µmol/L. Quantities whose units are identical (sodium mmol/L = mEq/L) or have a
single unit (age in years, heart rate in beats/min, SpO2 in %) accept a bare number.
Unit spellings are matched case-insensitively and ignore spaces; `µ`, `μ` and `u` are the
same (`umol/L`), °C also accepts `C`, `degC`, `Cel`, and °F accepts `F`, `degF`, `[degF]`.

| Quantity | Canonical unit | Accepted alternative | Conversion |
| --- | --- | --- | --- |
| Creatinine | mg/dL | µmol/L | mg/dL = µmol/L / 88.4 |
| Bilirubin | mg/dL | µmol/L | mg/dL = µmol/L / 17.1 |
| Albumin | g/dL | g/L | g/dL = g/L / 10 |
| Urea (CURB-65) | mmol/L (urea) | mg/dL (blood urea nitrogen, BUN) | urea mmol/L = BUN mg/dL x 0.357 |
| Sodium | mmol/L | mEq/L | identity |
| Temperature | °C | °F | °C = (°F - 32) x 5/9 |

Converted values are rounded to 6 decimal places so float noise cannot cross a cut-off
(100.4 °F is exactly 38.0 °C, which is not "> 38 °C"). The result's `inputs` echo shows
the canonical value and, when converted, the value and unit you reported.

**Physiological ranges.** Every quantity has an allowed range in its canonical unit (for
example age 18-120 years for adult scores and 3-120 for Centor, heart rate 20-300/min,
SpO2 50-100%, temperature 25-45 °C, creatinine 0.1-25 mg/dL, bilirubin 0.1-80 mg/dL,
albumin 0.5-7 g/dL, INR 0.5-20, sodium 100-180 mmol/L). A value outside the range is
rejected; it usually means a unit mix-up (88 µmol/L sent as mg/dL) or a typo.

**Never a silent default.** A missing required input is an error. Booleans are never
assumed `false` when absent, because "not recorded" is not "absent". The only optional
input is NEWS2 `spo2_scale` (default `scale_1`); the result's `inputs` echo marks it
`"defaulted": true`.

Validation collects every problem into one message such as:

```text
Invalid inputs for ckd_epi_2021: inputs.creatinine needs an explicit unit: {"value": <number>, "unit": "mg/dL" | "µmol/L"}; inputs.sex is required
```

| Problem | Message |
| --- | --- |
| Missing input | `inputs.<name> is required` |
| Unknown input name | `inputs has unexpected properties (allowed: ...)` (the unknown name is not echoed) |
| Bare number where a unit is needed | `inputs.<name> needs an explicit unit: {...}` |
| Unsupported unit | `inputs.<name>.unit must be one of ...` |
| Not a finite number | `inputs.<name> must be a finite number` / `inputs.<name>.value must be a finite number` |
| Fraction for an integer input | `inputs.<name> must be a whole number` |
| Out of range | `inputs.<name> must be between <min> and <max> <unit>` |
| Wrong boolean / choice | `inputs.<name> must be true or false` / `inputs.<name> must be one of ...` |

Messages name the input and the rule but never echo the value you sent.

## HTTP API reference

All three endpoints are under the `Clinical calculators (research use only)` tag of the
OpenAPI docs (`/docs`). Errors use medagent's `{"detail": "<message>"}` shape.

### `GET /calculators`

Lists the calculators. Query parameter `category` (optional): one of `cardiology`,
`critical care`, `hepatology`, `infectious disease`, `nephrology`, `neurology`,
`pulmonology`; anything else is a 422.

Response: `count`, `categories`, `calculators[]` (each with `id`, `name`, `version`,
`category`, `purpose`, `score_unit`, `score_range`, `wraps` — the wrapped scorer class —
`inputs[]` with `name`, `type`, `required`, `unit`, `accepted_units`, `unit_required`,
`choices`, `minimum`, `maximum`, `default`, `description`, `bands[]` with `band` and
`range`, and `citation`), and `disclaimer`.

### `GET /calculators/{calculator_id}`

The full specification: everything in the listing plus, per input, `label`, the
conversion of each accepted unit (`to_canonical`, e.g. `mg/dL = µmol/L / 88.4`) and the
range; `input_schema` (a JSON Schema for `inputs`), every band with its `label`,
`description` and `severity`, all `citations` and the `limitations`. Unknown id: 404.

### `POST /calculators/{calculator_id}`

Body: `{"inputs": {...}}` (exactly that one key), at most 64 KiB. Returns the
[result](#result-reference) with `Cache-Control: no-store`.

| Status | When |
| --- | --- |
| 200 | Computed. |
| 400 | The body is not valid JSON (including `NaN` / `Infinity`). |
| 404 | Unknown calculator id (the id is not echoed). |
| 413 | The body exceeds 64 KiB. |
| 422 | Not a `{"inputs": {...}}` object, or missing, malformed or out-of-range inputs; or the result matched prohibited prescription language (withheld, SAFETY.md §3.3). |

## MCP reference

`python -m medagent.mcp` serves both protocol eras (stateless `2026-07-28` and the
`initialize` handshake, see the [MCP server guide](MCP_SERVER_GUIDE.md)). Both tools are
read-only (`readOnlyHint: true`, `openWorldHint: false`), validate their arguments against
the advertised `inputSchema` and return `structuredContent` plus a one-line text summary.

| Tool | Arguments | Returns |
| --- | --- | --- |
| `list_calculators` | `category` (optional enum), `calculator_id` (optional enum) | The same object as `GET /calculators`, filtered. |
| `run_calculator` | `calculator_id` (required enum of the 13 ids), `inputs` (required object) | The [result](#result-reference); the text summary names the score, band and disclaimer. |

Invalid arguments — an unknown `calculator_id`, a missing `inputs`, or any calculator
input problem from the table above — return `isError: true` with the message and the
mandatory disclaimer, never a partial result. The MCP audit log (`--audit-log`) records
the tool, era, error kind, timing and an `inputs_hash`, never the values.

## Result reference

| Field | Meaning |
| --- | --- |
| `calculator` | `id`, `name` and `version` of the calculator that ran. |
| `score` | The total: points (an integer whenever it is whole), or for CKD-EPI 2021 the unrounded eGFR in mL/min/1.73 m2. The band is chosen from this full-precision value, so 59.88 is G3a, not 60 / G2, and no rounding can cross an eGFR threshold downstream. |
| `score_unit`, `score_range` | Unit and possible range of `score`. |
| `interpretation` | The band that contains `score`: `band` (stable id), `label`, `range`, `description` (the risk stratum from the cited source) and `severity` (`LOW`, `MODERATE`, `HIGH`, `CRITICAL`). |
| `components[]` | One entry per criterion: `criterion` id (the wrapped scorer's factor name where one exists), `label`, `points` it contributed (`null` for formula terms), `rule` that fired, the `inputs` it used and, for MELD-Na and CKD-EPI, the `value` of the term or factor. |
| `details` | Calculator-specific extras: Wells PE `two_tier` (`pe_unlikely` <= 4 / `pe_likely` > 4), MELD-Na `meld_i` and `sodium_term_applied`, CKD-EPI `egfr_rounded` (the whole number laboratories report, for display only). |
| `inputs` | Echo of the validated inputs in canonical units; converted quantities also show the `reported` value and unit, defaulted ones `"defaulted": true`. |
| `citations[]` | `reference`, `doi`, `pmid`, `url`. |
| `limitations[]` | What the calculator does not cover; read them before relying on a band. |
| `disclaimer` | The mandatory research-use disclaimer. |

A complete, real `POST /calculators/qsofa` response for
`{"inputs": {"respiratory_rate": 24, "systolic_bp": 95, "altered_mentation": false}}`:

```json
{
  "calculator": {
    "id": "qsofa",
    "name": "qSOFA (quick Sequential Organ Failure Assessment)",
    "version": "1.0.0"
  },
  "score": 2,
  "score_unit": "points",
  "score_range": "0-3",
  "interpretation": {
    "band": "positive",
    "label": "qSOFA >= 2",
    "range": "2-3",
    "description": "Outside the ICU, in-hospital mortality was 3- to 14-fold higher than with qSOFA < 2 across baseline-risk deciles (Seymour 2016).",
    "severity": "HIGH"
  },
  "components": [
    {
      "criterion": "respiratory_rate_ge_22",
      "label": "Respiratory rate >= 22/min",
      "points": 1,
      "rule": "respiratory_rate 24 /min >= 22: +1",
      "inputs": [
        "respiratory_rate"
      ]
    },
    {
      "criterion": "altered_mentation",
      "label": "Altered mentation (GCS < 15)",
      "points": 0,
      "rule": "altered_mentation false: 0",
      "inputs": [
        "altered_mentation"
      ]
    },
    {
      "criterion": "systolic_bp_le_100",
      "label": "Systolic BP <= 100 mmHg",
      "points": 1,
      "rule": "systolic_bp 95 mmHg <= 100: +1",
      "inputs": [
        "systolic_bp"
      ]
    }
  ],
  "details": {},
  "inputs": {
    "respiratory_rate": {
      "value": 24,
      "unit": "breaths/min"
    },
    "systolic_bp": {
      "value": 95,
      "unit": "mmHg"
    },
    "altered_mentation": {
      "value": false
    }
  },
  "citations": [
    {
      "reference": "Seymour CW, Liu VX, Iwashyna TJ, et al. Assessment of clinical criteria for sepsis: for the Third International Consensus Definitions for Sepsis and Septic Shock (Sepsis-3). JAMA. 2016;315(8):762-774.",
      "doi": "10.1001/jama.2016.0288",
      "pmid": "26903335",
      "url": null
    }
  ],
  "limitations": [
    "qSOFA is a prognostic prompt, not a diagnostic criterion for sepsis, and is not recommended as a single screening tool (Surviving Sepsis Campaign 2021).",
    "The wrapped QSofaSepsisScreenScorer labels one criterion 'moderate'; the calculator reports the published two-way interpretation."
  ],
  "disclaimer": "⚠️  RESEARCH USE ONLY. This output is generated by an AI system and has NOT been reviewed by a licensed clinician. It is NOT FDA-cleared and MUST NOT be used to guide clinical treatment decisions. Always consult a qualified healthcare professional for medical advice, diagnosis, or treatment."
}
```

## How an LLM agent should call the calculators

The point of the registry is that the model **extracts and verifies values** and the tool
**does the clinical arithmetic**. A reliable loop for GPT-6.2 Sol, Claude Opus 5.5,
Gemini 4 Neon or Kimi K3.1 Pro (any MCP-capable client; OpenAI tool calling goes through
the Responses API):

1. Call `list_calculators` once (or with `category` / `calculator_id`) and read the input
   specs: names, types, units, ranges and choices.
2. Extract each value from the record **with its unit** and send it as
   `{"value", "unit"}`; never convert units in the prompt.
3. If a required value is not documented, do not guess and do not send `false`: ask the
   clinician or report that the score cannot be computed. Clinician-judgement inputs
   (CURB-65 confusion, Wells "PE most likely", HEART history and ECG, Child-Pugh ascites
   and encephalopathy grade) must come from the record, not from the model's opinion.
4. Call `run_calculator`. On `isError`, fix exactly the inputs the message names and retry.
5. Quote the result faithfully: score, band label and description, the components that
   scored, the citation and the limitations. Present it as research information for a
   clinician, never as a treatment decision.

A system-prompt snippet that works well:

```text
For any clinical score or equation, call run_calculator instead of computing it. Pass every
quantity with its unit exactly as documented. If a required input is missing, say so and
stop; never assume a finding is absent. Report the score, the interpretation band, the
criteria that scored and the citation, and state that this is research information that a
clinician must verify. Never turn a score into a treatment recommendation.
```

## Worked examples

All outputs below are real; the first three come from the demo transcript.

**CURB-65 with BUN in mg/dL** — BUN 26 mg/dL is converted to urea 9.28 mmol/L:

```text
score 3 -> High risk (3-5)
  0  confusion false: 0
  1  urea 9.28 mmol/L > 7: +1
  1  respiratory_rate 31 /min >= 30: +1
  0  systolic_bp 118 mmHg >= 90; diastolic_bp 72 mmHg > 60: 0
  1  age 72 years >= 65: +1
```

**MELD-Na in SI units** (bilirubin 42.75 µmol/L, INR 1.8, creatinine 168 µmol/L, Na 129):

```text
MELD-Na 27: 3-month mortality 19.6% (Wiesner 2003).
  creatinine 1.9 -> 1.9 (bounded 1.0-4.0): 0.957 x ln(creatinine) = 0.614
  bilirubin 2.5 -> 2.5 (floor 1.0): 0.378 x ln(bilirubin) = 0.346
  inr 1.8 -> 1.8 (floor 1.0): 1.120 x ln(INR) = 0.658
  0.614 + 0.346 + 0.658 + 0.643 = 2.262 -> 2.3 x 10 = MELD(i) 23
  sodium 129 -> 129 (bounded 125-137): 1.32 x 8 - 0.033 x 23 x 8 = 4.488
```

**CKD-EPI 2021** (creatinine 1.3 mg/dL, 67-year-old woman; the band uses the unrounded
value, `details.egfr_rounded` is what a laboratory would report):

```json
{"score":45.069939342314576,"egfr_rounded":45,"band":"G3a mildly to moderately decreased","doi":"10.1056/NEJMoa2102953"}
```

**NEWS2 with a temperature in °F, over MCP** (`run_calculator` text summary):

```text
NEWS2 (National Early Warning Score 2): 7 points -> High clinical risk (7-20). Aggregate 7 or more (emergency response threshold). RESEARCH USE ONLY: verify the inputs; not a substitute for clinical judgement.
```

**A single red score** — every NEWS2 parameter normal except consciousness `voice`:
`score` 3, `interpretation.band` `low_medium` (before this feature the scorer said `low`).

**Wells PE at exactly 6.0** (clinical DVT signs + PE most likely): `score` 6,
`interpretation.band` `moderate`, `details.two_tier` `pe_likely`.

## Audit results

Before exposing a calculator, its point weights, thresholds (inclusive vs exclusive), unit
handling and bands were checked against the original publication and the MedCalc-Bench
reference implementation. Four existing scorers were wrong; each was fixed test-first
(`test(safety): reproduce ...` then `fix(safety): ...`) and keeps its public API.

| Calculator | Checked against | Result |
| --- | --- | --- |
| CURB-65 | Lim 2003; MedCalc-Bench `curb_65.py` | Correct. BUN is converted exactly (7 mmol/L = 19.6 mg/dL); MedCalc-Bench and MDCalc use the rounded "BUN > 19 mg/dL". |
| CHA2DS2-VASc | Lip 2010; MedCalc-Bench | Correct weights and Lip 2010 bands; the sex-modifier reading of later guidelines is a listed limitation. |
| HAS-BLED | Pisters 2010; MedCalc-Bench | Correct (elderly is age > 65). |
| HEART | Six 2008; MedCalc-Bench | Correct; troponin points use the ratio to the upper reference limit (<= 1, <= 3, > 3). |
| Wells PE | Wells 2000 | **Bug fixed:** a score of exactly 6.0 was banded high; Wells 2000 defines moderate as 2.0-6.0 and high as > 6.0. |
| PERC | Kline 2004; MedCalc-Bench | Correct criteria; the calculator reports the published negative/positive reading instead of the scorer's extra `near_miss` label. |
| qSOFA | Seymour 2016 | Correct; the calculator reports the published < 2 / >= 2 reading. |
| NEWS2 | RCP 2017 chart | **Bug fixed:** a 3 in any single parameter with an aggregate of 0-4 is low-medium risk; the scorer reported low. |
| MELD-Na | Kim 2008, OPTN 2016 policy; MedCalc-Bench `meldna.py` | **Bug fixed:** `MeldNaScorer` summed five 0/1 flags (0-5) against MELD cut-offs, so every patient was "low". It now computes the OPTN MELD-Na. MedCalc-Bench applies the dialysis rule only when creatinine is 1.0-4.0, so a dialysed patient with creatinine < 1.0 keeps 1.0; medagent follows OPTN (always 4.0). |
| Child-Pugh | Pugh 1973 with INR cut-offs; MedCalc-Bench | Correct, same inclusive boundaries (bilirubin 2-3, albumin 2.8-3.5, INR 1.7-2.3 score 2). |
| GCS | Teasdale 1974 | Correct; bands are the conventional head-injury classification. |
| Centor (McIsaac) | McIsaac 1998 | **Bug fixed:** the -1 point for age >= 45 was rejected (adults >= 45 were over-scored by one). |
| CKD-EPI 2021 | Inker 2021; MedCalc-Bench `ckd-epi_2021_creatinine.py` | New. MedCalc-Bench uses kappa 0.7 for men with creatinine <= 0.9 mg/dL; Inker 2021 uses 0.9 (a 60-year-old man with 0.8 mg/dL: 101 here, 94 there). |

Fail-before evidence for the four fixes:

```text
test_score_of_exactly_six_is_moderate_not_high        AssertionError: assert 'high' == 'moderate'
test_single_parameter_red_score_is_low_medium         AssertionError: assert 'low' == 'low_medium'
test_mcisaac_age_45_or_older_subtracts_one_point      ValueError: age_bonus must be 0 or 1
test_all_five_abnormal_flags_are_not_low_risk         AssertionError: assert 'low' == 'high'
```

`MeldNaScorer` keeps its flag-based `MeldNaFactors` fields; with only flags it now reports
the lowest MELD-Na consistent with them (labelled a lower bound in the rationale) and gains
optional raw-lab fields (`bilirubin_mg_dl`, `inr`, `creatinine_mg_dl`, `sodium_mmol_l`)
for the exact score.

## Configuration

None. The calculators add no settings, environment variables or files; they need no LLM
provider, network or database, and they run in the API process and the MCP server alike.

## How it fits with the rest of medagent

- **Safety scorers.** The calculators wrap the existing scorers instead of duplicating
  their arithmetic; existing callers of `*_scorer.py` are unaffected (apart from the four
  corrected results above).
- **Medication screening.** `screen_medications` takes an `egfr`; an agent can compute it
  with `run_calculator("ckd_epi_2021", ...)` first instead of estimating it, passing the
  unrounded `score` (the renal dosing thresholds are inclusive).
- **Safety controls.** Results pass the same prescription-language output guard as the
  other tools (SAFETY.md §3.3) and carry the mandatory disclaimer (§3.1).
- **Logging.** The registry logs `calculator_run` (calculator id and band) and
  `calculator_rejected` (calculator id and the number of problems). The wrapped scorers
  keep their existing `<scorer>_scored` events (total and band). Inputs are never logged.
- **CDS Hooks.** Not wired yet; a calculator card is on the roadmap.

## Safety and limitations

- Research use only; not a substitute for clinical judgement, not FDA-cleared, not
  validated for clinical deployment.
- Inputs must be verified by a clinician: the calculators trust the values they are given
  and cannot detect a plausible but wrong value inside the physiological range.
- Bands describe risk strata reported by the cited studies, in their populations; they do
  not say what to do. No result is a treatment, admission or anticoagulation decision.
- Several inputs are clinician judgements (confusion, "PE most likely", HEART history and
  ECG, ascites and encephalopathy grades, NEWS2 SpO2 Scale 2); a model must not invent them.
- Each calculator lists its own limitations (population, validation setting, deviations
  from the original publication); they are returned with every result.

## Limitations and roadmap

Deliberately left out of this release:

- **More calculators.** Revised Geneva and Glasgow-Blatchford scorers exist but are not yet
  audited and exposed; Wells DVT, PESI, SOFA, MELD 3.0, Cockcroft-Gault and CHA2DS2-VA are
  candidates.
- **CDS Hooks card.** A CHA2DS2-VASc / HAS-BLED card on `order-select` for anticoagulants.
- **FHIR input mapping.** Filling lab inputs from FHIR `Observation` resources by LOINC code
  (creatinine, bilirubin, albumin, INR, sodium) with UCUM units.
- **Trends.** NEWS2 is designed for repeated observations; the calculator scores one set.
- **Audit trail.** Calculator runs are logged but not persisted to the audit database.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `needs an explicit unit` | Send `{"value": 1.3, "unit": "mg/dL"}` instead of `1.3` for creatinine, bilirubin, albumin, urea and temperature. |
| `must be between ...` for a plausible value | Usually a unit mix-up (µmol/L sent as mg/dL, °F as °C). Send the unit you have. |
| `is required` for a finding that is absent | Send `false`; absence must be stated, never implied. |
| `inputs has unexpected properties` | A misspelt input name; `GET /calculators/{id}` lists the exact names. |
| `must be true or false` | Booleans must be JSON `true` / `false`, not `0` / `1` or strings. |
| 404 on `POST /calculators/{id}` | Unknown id; ids are lowercase with underscores (`curb_65`, `ckd_epi_2021`). |
| 422 `{"inputs": {...}}` | The body must be an object with exactly one key, `inputs`. |
| MCP `Invalid arguments: arguments.calculator_id ...` | Use an id from `list_calculators`; the tool schema enumerates them. |

## FAQ

**Why are thresholds sometimes different from MDCalc?** MDCalc rounds some converted
cut-offs (BUN > 19 mg/dL); medagent applies the publication's cut-off in its own unit and
converts exactly. Differences are listed per calculator under `limitations`.

**Can I pass a value without a unit?** Only where the unit is unambiguous (age, heart
rate, SpO2, sodium, INR, GCS components).

**Why is a missing boolean an error instead of `false`?** Because an LLM that cannot find
"hemoptysis" in a note has not established that the patient has no hemoptysis; silently
scoring it 0 is the error MedCalc-Bench measures.

**Is the result safe to show a patient?** No. It is research information for clinicians and
health-AI engineers, carrying the mandatory disclaimer.

**How do I add a calculator?** Define its inputs, bands, citations, limitations and an
`evaluate` function in `src/medagent/calculators/`, wrap an audited scorer where one
exists, register it in `registry.py`, and add worked-example and boundary tests.
