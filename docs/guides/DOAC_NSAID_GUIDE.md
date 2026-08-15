# DOAC + NSAID Bleeding Intensifier Checker Guide

*medagent-core — Safety Control #71*

![DOAC NSAID checker flow](../../assets/doac_nsaid_demo.gif)

## Overview

`DoacNsaidChecker` flags a direct oral anticoagulant (DOAC) co-prescribed with a
supported NSAID. Concurrent DOAC anticoagulation with an NSAID intensifies major
bleeding risk through anticoagulation plus GI mucosal injury and platelet
dysfunction.

Findings are advisory `DoacNsaidRisk` records — **RESEARCH USE ONLY** — and the
checker is exported from `medagent.safety`.

## Medication panels

| Class | Agents |
|---|---|
| DOAC | apixaban, rivaroxaban, edoxaban, dabigatran |
| NSAID | ibuprofen, naproxen, diclofenac, ketorolac, meloxicam, celecoxib |

Ketorolac findings are **CRITICAL**. Other panel NSAIDs are **HIGH**. Aspirin
is intentionally excluded because DOAC + antiplatelet screening is a separate
control.

Every unique DOAC × NSAID pair across separate medication entries yields one
finding. Matching is whole-token based, duplicates are de-duplicated by
canonical pair, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import DoacNsaidChecker

findings = DoacNsaidChecker().check(
    medications=[
        Medication(name="Apixaban 5 mg BID"),
        Medication(name="Ibuprofen 400 mg TID"),
    ],
)
for finding in findings:
    print(finding.agent, finding.partner_agent, finding.severity)
```

## Scope boundaries

This control targets DOAC + NSAID bleed intensification. It does not replace
DOAC + antiplatelet screening, warfarin + NSAID controls, or NSAID + SSRI/SNRI
bleeding checks. It never changes therapy; obtain qualified clinical review.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.71](../../SAFETY.md)
- [README safety controls table](../../README.md)
- DOAC + antiplatelet: `safety/doac_antiplatelet_checker.py`
