# Tramadol + SSRI/SNRI Seizure/Serotonin Dual-Risk Checker Guide

*medagent-core — Safety Control #51*

![Tramadol SSRI checker flow](../../assets/tramadol_ssri_demo.gif)

## Overview

`TramadolSsriChecker` flags **tramadol / ultram** co-prescribed with an
**SSRI or SNRI** antidepressant — a combination that elevates seizure risk and
serotonergic toxicity. Tramadol lowers the seizure threshold and is itself
serotonergic; stacking with SSRI/SNRI agents compounds both hazards. This check
complements MAOI serotonin cross-checks and broad serotonin-syndrome screening.

Findings are advisory `TramadolSsriRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`. Severity is always
**HIGH**.

## Tramadol panel

| Agent | Notes |
|---|---|
| tramadol | opioid analgesic; serotonergic; lowers seizure threshold |
| ultram | tramadol brand |

## SSRI / SNRI partners

| Agent | Class |
|---|---|
| sertraline | SSRI |
| fluoxetine | SSRI |
| paroxetine | SSRI |
| citalopram | SSRI |
| escitalopram | SSRI |
| venlafaxine | SNRI |
| duloxetine | SNRI |

Every tramadol × SSRI/SNRI pair yields one finding. Medication matching is
whole-token based.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import TramadolSsriChecker

findings = TramadolSsriChecker().check(
    medications=[
        Medication(name="Tramadol 50 mg Q6H"),
        Medication(name="Sertraline 50 mg daily"),
    ],
)
for finding in findings:
    print(
        finding.agent,
        finding.partner_agent,
        finding.partner_drug_class,
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

**Topics:** `medical-ai`, `drug-safety`, `tramadol`, `agentic-ai`, `python`

## See also

- [SAFETY.md §3.51](../../SAFETY.md)
- [README safety controls table](../../README.md)
- MAOI serotonin cross-check: `safety/maoi_serotonin_checker.py`
