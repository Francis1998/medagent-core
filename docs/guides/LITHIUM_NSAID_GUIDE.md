# Lithium + NSAID Toxicity Checker Guide

*medagent-core — Safety Control #55*

![Lithium NSAID checker flow](../../assets/lithium_nsaid_demo.gif)

## Overview

`LithiumNsaidChecker` flags **lithium-class agents** (lithium, Lithobid,
Eskalith) co-prescribed with **NSAIDs** (ibuprofen, naproxen, diclofenac,
indomethacin, ketorolac, meloxicam, piroxicam, celecoxib). NSAIDs can reduce
renal lithium clearance and raise lithium serum concentrations, increasing
lithium toxicity risk.

Findings are advisory `LithiumNsaidRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`. Severity is always
**HIGH**.

## Lithium-class panel

| Agent | Notes |
|---|---|
| lithium | mood stabilizer |
| lithobid | lithium brand |
| eskalith | lithium brand |

## NSAID partners

| Agent | Notes |
|---|---|
| ibuprofen | NSAID |
| naproxen | NSAID |
| diclofenac | NSAID |
| indomethacin | NSAID |
| ketorolac | NSAID |
| meloxicam | NSAID |
| piroxicam | NSAID |
| celecoxib | COX-2 selective NSAID |

**Not included:** acetaminophen / paracetamol (not NSAIDs).

Every lithium × NSAID pair yields one finding. Medication matching is
whole-token based.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import LithiumNsaidChecker

findings = LithiumNsaidChecker().check(
    medications=[
        Medication(name="Lithium carbonate 300 mg BID"),
        Medication(name="Ibuprofen 400 mg TID PRN"),
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

**Topics:** `medical-ai`, `drug-safety`, `lithium`, `nsaid`, `agentic-ai`,
`python`

## See also

- [SAFETY.md §3.55](../../SAFETY.md)
- [README safety controls table](../../README.md)
