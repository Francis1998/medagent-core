# Digoxin + Verapamil Toxicity Checker Guide

*medagent-core — Safety Control #66*

![Digoxin verapamil checker flow](../../assets/digoxin_verapamil_demo.gif)

## Overview

`DigoxinVerapamilChecker` flags digoxin co-prescribed with verapamil.
Verapamil inhibits P-glycoprotein and reduces digoxin clearance, raising
digoxin toxicity risk.

Findings are advisory `DigoxinVerapamilRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`. Severity is always
**HIGH**.

## Digoxin panel

| Agents |
|---|
| digoxin, lanoxin |

## Verapamil partners

| Agents |
|---|
| verapamil, calan, isoptin, verelan |

Every unique digoxin × verapamil pair across separate medication entries yields
one finding. Matching is whole-token based, duplicates are de-duplicated by
canonical pair, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import DigoxinVerapamilChecker

findings = DigoxinVerapamilChecker().check(
    medications=[
        Medication(name="Digoxin 0.125 mg daily"),
        Medication(name="Verapamil 120 mg BID"),
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

## Scope boundaries

This control targets the digoxin × verapamil P-gp / clearance pair.
Digoxin + amiodarone monitoring belongs to `DigoxinAmioChecker`; macrolide +
digoxin P-gp screening belongs to `MacrolideDigoxinChecker`. This control does
not replace digoxin level assessment or qualified clinical review, and it never
changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.66](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Digoxin + amiodarone: `safety/digoxin_amio_checker.py`
- Macrolide + digoxin: `safety/macrolide_digoxin_checker.py`
