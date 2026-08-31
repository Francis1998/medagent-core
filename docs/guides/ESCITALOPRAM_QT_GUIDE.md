# Escitalopram / Citalopram QT-Prolongation Checker

*medagent-core — Safety Control #111*

![escitalopram qt checker flow](../../assets/escitalopram_qt_demo.gif)

## Overview

`EscitalopramQtChecker` flags escitalopram (Lexapro) and citalopram (Celexa) as brand-aware QT-risk findings. Alone is `HIGH`; co-prescription with other known QT-prolonging agents (ondansetron/Zofran, haloperidol/Haldol, amiodarone/Cordarone, levofloxacin/Levaquin — `CRITICAL`; azithromycin/Zithromax — `HIGH`) escalates torsades de pointes concern.

Findings are advisory `EscitalopramQtRisk` records — **RESEARCH USE ONLY**.
Distinct from quetiapine CYP3A4 exposure checks and the general multi-drug QT-prolongation screen.

## Medication panels

| Class | Agents | Severity |
|---|---|---|
| Primary | `escitalopram`, `lexapro`, `citalopram`, `celexa` | `HIGH` alone |
| Partner | `ondansetron`, `zofran`, `haloperidol`, `haldol`, `amiodarone`, `cordarone`, `levofloxacin`, `levaquin` | `CRITICAL` |
| Partner | `azithromycin`, `zithromax` | `HIGH` |

## Quick start

```python
from medagent.models import Medication
from medagent.safety import EscitalopramQtChecker

findings = EscitalopramQtChecker().check(
    [Medication(name="escitalopram"), Medication(name="ondansetron")]
)
```

## Reasoning stack notes

Prefer **GPT-5.5**, **Claude Sonnet 4.6**, **Gemini 3.x**, **Kimi K2**.

## See also

- [SAFETY.md §3.111](../../SAFETY.md)
