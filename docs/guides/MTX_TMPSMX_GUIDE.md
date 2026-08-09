# Methotrexate + TMP-SMX Toxicity Checker Guide

*medagent-core — Safety Control #56*

![Methotrexate TMP-SMX checker flow](../../assets/mtx_tmpsmx_demo.gif)

## Overview

`MtxTmpsmxChecker` flags **methotrexate** co-prescribed with **TMP-SMX /
co-trimoxazole panel agents** (trimethoprim, sulfamethoxazole, bactrim, septra,
cotrimoxazole). Trimethoprim–sulfamethoxazole can potentiate methotrexate
antifolate toxicity and increase myelosuppression risk.

Findings are advisory `MtxTmpsmxRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`. Severity is always
**CRITICAL**.

## Methotrexate panel

| Agent | Notes |
|---|---|
| methotrexate | antifolate immunosuppressant / antineoplastic |

## TMP-SMX partners

| Agent | Notes |
|---|---|
| trimethoprim | DHFR inhibitor component of TMP-SMX |
| sulfamethoxazole | sulfonamide component of TMP-SMX |
| bactrim | TMP-SMX brand |
| septra | TMP-SMX brand |
| cotrimoxazole | TMP-SMX / co-trimoxazole |

Every methotrexate × TMP-SMX pair yields one finding. Medication matching is
whole-token based.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import MtxTmpsmxChecker

findings = MtxTmpsmxChecker().check(
    medications=[
        Medication(name="Methotrexate 15 mg weekly"),
        Medication(name="Bactrim DS one tablet BID"),
    ],
)
for finding in findings:
    print(
        finding.agent,
        finding.partner_agent,
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

**Topics:** `medical-ai`, `drug-safety`, `methotrexate`, `tmp-smx`, `agentic-ai`,
`python`

## See also

- [SAFETY.md §3.56](../../SAFETY.md)
- [README safety controls table](../../README.md)
