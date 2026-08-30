# Midazolam + Strong CYP3A4 Inhibitor Sedation Checker

*medagent-core — Safety Control #108*

![midazolam_cyp3a4 checker flow](../../assets/midazolam_cyp3a4_demo.gif)

## Overview

`MidazolamCyp3a4Checker` flags midazolam CYP3A4 co-prescription risks.
Strong CYP3A4 inhibition can elevate midazolam exposure and prolong
sedation / respiratory depression.

Findings are advisory `MidazolamCyp3a4Risk` records — **RESEARCH USE ONLY**.
Distinct from fentanyl, quetiapine, and ivabradine CYP3A4 exposure checkers.

## Medication panels

| Class | Agents | Severity |
|---|---|---|
| Primary | `midazolam` | — |
| Primary | `versed` | — |
| Partner | `ketoconazole` | `CRITICAL` |
| Partner | `clarithromycin` | `CRITICAL` |
| Partner | `ritonavir` | `CRITICAL` |
| Partner | `itraconazole` | `CRITICAL` |
| Partner | `nefazodone` | `CRITICAL` |

## Quick start

```python
from medagent.models import Medication
from medagent.safety import MidazolamCyp3a4Checker

findings = MidazolamCyp3a4Checker().check(
    [Medication(name="midazolam"), Medication(name="ketoconazole")]
)
```

## Reasoning stack notes

Prefer **GPT-5.5**, **Claude Sonnet 4.6**, **Gemini 3.x**, **Kimi K2**.

## See also

- [SAFETY.md §3.108](../../SAFETY.md)
