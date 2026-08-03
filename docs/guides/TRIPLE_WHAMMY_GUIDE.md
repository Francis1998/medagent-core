# Triple Whammy (NSAID + ACEI/ARB/ARNI + Diuretic) Checker Guide

*medagent-core — Safety Control #46*

![Triple whammy checker flow](../../assets/triple_whammy_demo.gif)

## Overview

`TripleWhammyChecker` flags concurrent **NSAID**, **ACEI/ARB/ARNI**, and
**loop or thiazide diuretic** therapy — the "triple whammy" combination that
impairs renal autoregulation and markedly increases acute kidney injury risk.
It complements generic drug-drug interaction and renal dose screening with a
focused three-class cross-check.

Findings are advisory `TripleWhammyRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`. Severity is always
**CRITICAL**.

## NSAID panel

| Agent | Notes |
|---|---|
| ibuprofen | NSAID |
| naproxen | NSAID |
| diclofenac | NSAID |
| ketorolac | NSAID |
| meloxicam | NSAID |

## ACEI / ARB / ARNI panel

| Agent | Notes |
|---|---|
| lisinopril | ACE inhibitor |
| enalapril | ACE inhibitor |
| ramipril | ACE inhibitor |
| losartan | ARB |
| valsartan | ARB |
| sacubitril | ARNI component |

## Diuretic panel

| Agent | Notes |
|---|---|
| furosemide | loop diuretic |
| bumetanide | loop diuretic |
| torsemide | loop diuretic |
| hctz | thiazide (abbreviation) |
| hydrochlorothiazide | thiazide |
| chlorthalidone | thiazide-like |

Every NSAID × ACEI/ARB/ARNI × diuretic triad yields one finding. Medication
matching is whole-token based.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import TripleWhammyChecker

findings = TripleWhammyChecker().check(
    medications=[
        Medication(name="Ibuprofen 400 mg TID"),
        Medication(name="Lisinopril 10 mg daily"),
        Medication(name="Furosemide 40 mg BID"),
    ],
)
for finding in findings:
    print(
        finding.nsaid_agent,
        finding.acei_arb_agent,
        finding.diuretic_agent,
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

## Suggested repo description / topics

**Description:** Research-only medical agent core with deterministic safety
checkers and modern LLM adapters (GPT-5.5, Claude Sonnet 4.6, Gemini 3.x,
Kimi K2).

**Topics:** `medical-ai`, `drug-safety`, `renal-risk`, `agentic-ai`, `python`

## See also

- [SAFETY.md §3.46](../../SAFETY.md)
- [README safety controls table](../../README.md)
