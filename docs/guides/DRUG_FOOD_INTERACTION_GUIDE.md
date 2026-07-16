# Drug–Food Interaction Checker Guide

*medagent-core — Safety Control #19*

## Overview

`DrugFoodInteractionChecker` flags well-established interactions between active
medications and dietary exposures (grapefruit, dairy/calcium, tyramine, alcohol).
It complements the drug–drug interaction path shown in the pipeline demos
([`assets/demo_drugcheck.svg`](../../assets/demo_drugcheck.svg),
[`assets/demo_pipeline.svg`](../../assets/demo_pipeline.svg)) by covering
*food and beverage* hazards that medication-only checks miss.

Findings are advisory `DrugFoodInteractionRisk` records — RESEARCH USE ONLY —
and the checker is standalone (not exported from `safety/__init__.py` or wired
into the orchestrator).

## Panel (conservative)

| Food category | Example dietary flags | Interacting agents | Severity |
|---|---|---|---|
| grapefruit | `grapefruit`, `grapefruit juice` | simvastatin, atorvastatin | HIGH |
| dairy | `dairy`, `milk`, `calcium` | tetracycline, doxycycline, minocycline, ciprofloxacin | MODERATE |
| tyramine | `tyramine`, `tyramine-rich foods` | phenelzine, tranylcypromine, isocarboxazid | CRITICAL |
| alcohol | `alcohol`, `ethanol` | metronidazole, disulfiram | HIGH |

Matching is whole-token (same style as the allergy and duplicate-therapy
checkers): `milkweed` does not match `milk`, and loose substrings never trigger.

## Quick start

```python
from medagent.models import Medication
from medagent.safety.drug_food_interaction_checker import DrugFoodInteractionChecker

findings = DrugFoodInteractionChecker().check(
    medications=[Medication(name="Simvastatin 20 mg"), Medication(name="Metformin")],
    dietary_flags=["grapefruit juice", "dairy"],
)
for finding in findings:
    print(finding.agent, finding.food_category, finding.severity, finding.rationale)
```

## Reasoning stack notes

When this checker’s findings are summarized by an upstream reasoning / routing
layer, prefer current frontier models for clinical prose:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.19](../../SAFETY.md)
- [README safety controls table](../../README.md)
- [CHANGELOG](../../CHANGELOG.md)
- Drug-check demo: [`assets/demo_drugcheck.svg`](../../assets/demo_drugcheck.svg)
