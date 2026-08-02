# Digoxin Toxicity Risk Checker Guide

*medagent-core — Safety Control #43*

![Digoxin toxicity checker flow](../../assets/digoxin_toxicity_demo.gif)

## Overview

`DigoxinToxicityChecker` flags **digoxin** when **hypokalemia**, **hypomagnesemia**,
or **loop diuretic co-prescription without K/Mg repletion cues** elevates toxicity
risk. It complements electrolyte × QT checking with a focused digoxin narrow
therapeutic index hazard assessment.

Findings are advisory `DigoxinToxicityRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`.

## Finding kinds

| Kind | Trigger | Severity |
|---|---|---|
| `low_potassium` | K &lt; 3.5 mmol/L | CRITICAL |
| `low_magnesium` | Mg &lt; 1.7 mg/dL | CRITICAL |
| `loop_diuretic_without_repletion` | Loop diuretic without K/Mg repletion cues | HIGH |

## Panels

| Role | Agents |
|---|---|
| digoxin | digoxin |
| loop diuretics | furosemide, bumetanide, torsemide |
| repletion cues | potassium, kcl, magnesium, spironolactone, eplerenone, amiloride, triamterene |

Medication matching is whole-token based.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import DigoxinToxicityChecker

findings = DigoxinToxicityChecker().check(
    medications=[
        Medication(name="Digoxin 0.125 mg daily"),
        Medication(name="Furosemide 40 mg BID"),
    ],
    potassium_mmol_l=3.2,
    magnesium_mg_dl=1.8,
)
for finding in findings:
    print(
        finding.agent,
        finding.finding_kind,
        finding.potassium_mmol_l,
        finding.magnesium_mg_dl,
        finding.loop_diuretic_agents_found,
        finding.repletion_agents_found,
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

## See also

- [SAFETY.md §3.43](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Electrolyte × QT checking: `safety/electrolyte_qt_checker.py`
