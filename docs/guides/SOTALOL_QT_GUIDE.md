# Sotalol QT-Prolongation Checker

*medagent-core — Safety Control #110*

![sotalol qt checker flow](../../assets/sotalol_qt_demo.gif)

## Overview

`SotalolQtChecker` flags sotalol therapy (sotalol, Betapace, Betapace AF, Sorine, Sotylize) as a brand-aware QT-risk finding. Sotalol alone is `HIGH`; co-prescription with other known QT-prolonging agents (ondansetron/Zofran, levofloxacin/Levaquin, haloperidol/Haldol, amiodarone/Cordarone — `CRITICAL`; azithromycin/Zithromax — `HIGH`) escalates torsades de pointes concern.

Findings are advisory `SotalolQtRisk` records — **RESEARCH USE ONLY**.
Distinct from the general multi-drug QT-prolongation screen and electrolyte QT checkers.

## Medication panels

| Class | Agents | Severity |
|---|---|---|
| Primary | `sotalol`, `betapace`, `betapace af`, `sorine`, `sotylize` | `HIGH` alone |
| Partner | `ondansetron`, `zofran`, `levofloxacin`, `levaquin`, `haloperidol`, `haldol`, `amiodarone`, `cordarone` | `CRITICAL` |
| Partner | `azithromycin`, `zithromax` | `HIGH` |

## Quick start

```python
from medagent.models import Medication
from medagent.safety import SotalolQtChecker

findings = SotalolQtChecker().check(
    [Medication(name="sotalol"), Medication(name="ondansetron")]
)
```

## Reasoning stack notes

Prefer **GPT-5.5**, **Claude Sonnet 4.6**, **Gemini 3.x**, **Kimi K2**.

## See also

- [SAFETY.md §3.110](../../SAFETY.md)
