# Methotrexate + NSAID Reduced-Clearance Checker Guide

*medagent-core — Safety Control #69*

![Methotrexate NSAID checker flow](../../assets/mtx_nsaid_demo.gif)

## Overview

`MtxNsaidChecker` flags methotrexate co-prescribed with a supported NSAID.
NSAIDs can reduce renal methotrexate elimination and increase exposure, raising
the risk of myelosuppression, mucositis, renal injury, and hepatotoxicity.

Findings are advisory `MtxNsaidRisk` records — **RESEARCH USE ONLY** — and the
checker is exported from `medagent.safety`.

## Medication panel

| Severity | NSAID partners |
|---|---|
| CRITICAL | indomethacin, ketorolac |
| HIGH | ibuprofen, naproxen, diclofenac |

Every unique methotrexate × NSAID pair across separate medication entries
yields one finding. Matching is whole-token based, duplicates are de-duplicated
by canonical pair, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import MtxNsaidChecker

findings = MtxNsaidChecker().check(
    medications=[
        Medication(name="Methotrexate 15 mg weekly"),
        Medication(name="Ketorolac 10 mg QID PRN"),
    ],
)
for finding in findings:
    print(finding.agent, finding.partner_agent, finding.severity)
```

## Scope boundaries

This is a deterministic co-prescription signal; it cannot infer indication,
methotrexate dose strategy, renal function, duration, or actual exposure.
Qualified clinical review remains essential. Methotrexate + TMP-SMX,
lithium + NSAID, and warfarin + NSAID hazards remain separate controls.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.69](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Methotrexate + TMP-SMX: `safety/mtx_tmpsmx_checker.py`
