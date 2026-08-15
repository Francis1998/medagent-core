# Clopidogrel + CYP2C19-Inhibiting PPI Checker Guide

*medagent-core — Safety Control #73*

![Clopidogrel PPI checker flow](../../assets/clopidogrel_ppi_demo.gif)

## Overview

`ClopidogrelPpiChecker` flags clopidogrel or Plavix co-prescribed with
omeprazole, esomeprazole, Prilosec, or Nexium. These PPIs inhibit CYP2C19,
reducing conversion of clopidogrel to its active metabolite and potentially
diminishing antiplatelet effect.

Findings are advisory `ClopidogrelPpiRisk` records — **RESEARCH USE ONLY** —
with **HIGH** severity. The checker is exported from `medagent.safety`.

## Medication panels

| Class | Agents |
|---|---|
| Clopidogrel | clopidogrel, plavix |
| CYP2C19-inhibiting PPI | omeprazole, esomeprazole, prilosec, nexium |

Pantoprazole and other PPIs with weaker CYP2C19 inhibition are intentionally
excluded from this focused panel.

Every unique clopidogrel × CYP2C19 PPI pair across separate medication entries
yields one finding. Matching is whole-token based, duplicates are de-duplicated
by canonical pair, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import ClopidogrelPpiChecker

findings = ClopidogrelPpiChecker().check(
    medications=[
        Medication(name="Clopidogrel 75 mg daily"),
        Medication(name="Omeprazole 20 mg daily"),
    ],
)
for finding in findings:
    print(finding.agent, finding.partner_agent, finding.severity)
```

## Scope boundaries

This control targets clopidogrel + omeprazole/esomeprazole CYP2C19 inhibition.
It does not replace DOAC + antiplatelet screening or generic PPI taper planning.
It never changes therapy; obtain qualified clinical review.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.73](../../SAFETY.md)
- [README safety controls table](../../README.md)
- DOAC + antiplatelet: `safety/doac_antiplatelet_checker.py`
