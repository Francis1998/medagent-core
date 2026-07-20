# FDA Black-Box Warning Checker Guide

*medagent-core — Safety Control #22*

![Black-box warning checker flow](../../assets/black_box_warning_demo.gif)

## Overview

`BlackBoxWarningChecker` flags active medications that match a curated panel of
agents with well-known **FDA boxed (black-box) warnings** — the agency's
strongest labelling caution.

It complements pregnancy, Beers/STOPP, interaction, and dose checkers by
surfacing *labelling-severity* risk that those checks do not key on.

Findings are advisory `BlackBoxWarningRisk` records — RESEARCH USE ONLY — and
the checker is standalone (not exported from `safety/__init__.py` or wired into
the orchestrator).

## Curated panel (conservative)

| Theme | Example agents | Typical severity |
|---|---|---|
| Fluoroquinolone | ciprofloxacin, levofloxacin, moxifloxacin, ofloxacin | HIGH |
| Clozapine | clozapine | CRITICAL |
| Retinoid | isotretinoin | CRITICAL |
| Antimetabolite | methotrexate | CRITICAL |
| Vitamin K antagonist | warfarin | HIGH |
| Biguanide | metformin | HIGH |
| Class III antiarrhythmic | amiodarone | CRITICAL |
| Antiepileptic | valproate / valproic, carbamazepine | CRITICAL / HIGH |
| Opioid analgesic | fentanyl, methadone, oxycodone, hydrocodone, morphine, hydromorphone | HIGH–CRITICAL |
| NSAID | ibuprofen, naproxen, diclofenac, ketorolac | MODERATE–HIGH |
| Thiazolidinedione | pioglitazone, rosiglitazone | HIGH |

Matching is whole-token (same style as the allergy and Beers checkers).

## Quick start

```python
from medagent.models import Medication
from medagent.safety.black_box_warning_checker import BlackBoxWarningChecker

findings = BlackBoxWarningChecker().check(
    medications=[
        Medication(name="Ciprofloxacin 500mg"),
        Medication(name="Clozapine 100mg"),
    ],
)
for finding in findings:
    print(
        finding.agent,
        finding.warning_theme,
        finding.severity,
        finding.rationale,
    )
```

## Reasoning stack notes

When this checker’s findings are summarized by an upstream reasoning / routing
layer, prefer current frontier models for clinical prose:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 2.5**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.22](../../SAFETY.md)
- [README safety controls table](../../README.md)
- [CHANGELOG](../../CHANGELOG.md)
