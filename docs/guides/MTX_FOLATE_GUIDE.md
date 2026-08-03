# Methotrexate Without Folate Co-therapy Checker Guide

*medagent-core — Safety Control #47*

![MTX folate checker flow](../../assets/mtx_folate_demo.gif)

## Overview

`MtxFolateChecker` flags **methotrexate** prescribed **without folic acid,
folate, or leucovorin** co-therapy — a preventable supportive-care gap that
increases mucositis and hematologic toxicity risk. It complements generic
drug-drug interaction screening with a focused antifolate co-therapy check.

Findings are advisory `MtxFolateRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`. Severity is always
**HIGH**.

## Methotrexate panel

| Agent | Notes |
|---|---|
| methotrexate | antifolate immunosuppressant / antineoplastic |

## Folate co-therapy cues (suppress findings)

| Agent | Notes |
|---|---|
| folic | folic acid (e.g. "Folic acid 1 mg") |
| folate | folate supplementation |
| leucovorin | folinic acid rescue / co-therapy |

Medication matching is whole-token based.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import MtxFolateChecker

findings = MtxFolateChecker().check(
    medications=[
        Medication(name="Methotrexate 15 mg weekly"),
        Medication(name="Prednisone 5 mg daily"),
    ],
)
for finding in findings:
    print(
        finding.agent,
        finding.severity,
        finding.rationale,
    )
```

## Reasoning stack notes

When this checker's findings are summarized by an upstream reasoning / routing
layer, prefer current frontier models for clinical prose:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## Suggested repo description / topics

**Description:** Research-only medical agent core with deterministic safety
checkers and modern LLM adapters (GPT-5.5, Claude Sonnet 4.6, Gemini 3.x,
Kimi K2).

**Topics:** `medical-ai`, `drug-safety`, `methotrexate`, `agentic-ai`, `python`

## See also

- [SAFETY.md §3.47](../../SAFETY.md)
- [README safety controls table](../../README.md)
