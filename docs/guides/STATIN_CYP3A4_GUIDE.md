# Statin + Strong CYP3A4 Inhibitor Checker Guide

*medagent-core — Safety Control #44*

![Statin CYP3A4 checker flow](../../assets/statin_cyp3a4_demo.gif)

## Overview

`StatinCyp3a4Checker` flags **simvastatin, lovastatin, and atorvastatin**
co-prescribed with **strong CYP3A4 inhibitors** — combinations that markedly
increase systemic statin exposure and the risk of myopathy and rhabdomyolysis.
It complements generic drug-drug interaction and drug-food grapefruit screening
with a focused statin × CYP3A4 inhibitor cross-check.

Findings are advisory `StatinCyp3a4Risk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`.

## Statin panel

| Agent | Severity when paired |
|---|---|
| simvastatin | CRITICAL |
| lovastatin | CRITICAL |
| atorvastatin | HIGH |

## Strong CYP3A4 inhibitor partners

| Agent | Notes |
|---|---|
| clarithromycin | macrolide antibiotic |
| itraconazole | azole antifungal |
| ketoconazole | azole antifungal |
| ritonavir | HIV protease inhibitor |
| grapefruit | dietary CYP3A4 inhibitor |

Every statin × inhibitor pair yields one finding. Medication matching is
whole-token based.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import StatinCyp3a4Checker

findings = StatinCyp3a4Checker().check(
    medications=[
        Medication(name="Simvastatin 40 mg nightly"),
        Medication(name="Clarithromycin 500 mg BID"),
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

## See also

- [SAFETY.md §3.44](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Drug-food grapefruit interactions: `safety/drug_food_interaction_checker.py`
