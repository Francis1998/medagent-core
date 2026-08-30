# Simvastatin + Amiodarone Myopathy/Rhabdomyolysis Checker

*medagent-core — Safety Control #107*

![simvastatin_amiodarone checker flow](../../assets/simvastatin_amiodarone_demo.gif)

## Overview

`SimvastatinAmiodaroneChecker` flags simvastatin amiodarone co-prescription risks.
Amiodarone inhibits CYP3A4-mediated simvastatin metabolism, increasing statin
exposure and myopathy/rhabdomyolysis risk (FDA dose-limit warning).

Findings are advisory `SimvastatinAmiodaroneRisk` records — **RESEARCH USE ONLY**.
Distinct from statin_fibrate and digoxin_amio interaction checkers.

## Medication panels

| Class | Agents | Severity |
|---|---|---|
| Primary | `simvastatin` | — |
| Primary | `zocor` | — |
| Partner | `amiodarone` | `CRITICAL` |
| Partner | `cordarone` | `CRITICAL` |

## Quick start

```python
from medagent.models import Medication
from medagent.safety import SimvastatinAmiodaroneChecker

findings = SimvastatinAmiodaroneChecker().check(
    [Medication(name="simvastatin"), Medication(name="amiodarone")]
)
```

## Reasoning stack notes

Prefer **GPT-5.5**, **Claude Sonnet 4.6**, **Gemini 3.x**, **Kimi K2**.

## See also

- [SAFETY.md §3.107](../../SAFETY.md)
