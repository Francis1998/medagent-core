# STOPP/START Checker Guide

*medagent-core — Safety Control #21*

![STOPP/START checker flow](../../assets/stopp_start_demo.gif)

## Overview

`StoppStartChecker` applies a curated mini-set of **STOPP** (stop/avoid) and
**START** (start/consider) criteria for adults aged **65 and older**. It
complements the AGS Beers Criteria checker: Beers is a single-agent PIM list,
while STOPP/START also covers *indication-conditioned* avoidances and *omitted*
indicated therapy.

Findings are advisory `StoppStartRisk` records — RESEARCH USE ONLY — and the
checker is standalone (not exported from `safety/__init__.py` or wired into the
orchestrator).

## Curated mini rule set

| Id | Type | Triggers when |
|---|---|---|
| STOPP-D1 | STOPP | Long-acting benzo (diazepam, chlordiazepoxide, flurazepam, clonazepam) |
| STOPP-D2 | STOPP | Tertiary TCA (amitriptyline, imipramine, doxepin) |
| STOPP-B1 | STOPP | Digoxin present (dose/renal review caution) |
| STOPP-H1 | STOPP | NSAID + heart failure / CHF / HFrEF |
| STOPP-K1 | STOPP | Long-acting sulfonylurea (glyburide / chlorpropamide) |
| START-A5 | START | Secondary prevention indication (MI / ASCVD / stroke / CAD) without a statin |
| START-A6 | START | Heart failure without ACE inhibitor or ARB |
| START-A1 | START | Atrial fibrillation without anticoagulant |

Matching is whole-token for medications and phrase/token-aware for conditions.
Patients under 65 (or unknown age) yield no findings.

## Quick start

```python
from medagent.models import Medication
from medagent.safety.stopp_start_checker import StoppStartChecker

findings = StoppStartChecker().check(
    medications=[
        Medication(name="Diazepam 5mg"),
        Medication(name="Metformin 500mg"),
    ],
    age=78,
    conditions=["Prior myocardial infarction"],
)
for finding in findings:
    print(
        finding.criterion_id,
        finding.criterion_type,
        finding.agent,
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

- [SAFETY.md §3.21](../../SAFETY.md)
- [README safety controls table](../../README.md)
- [CHANGELOG](../../CHANGELOG.md)
- Beers Criteria: `safety/beers_criteria_checker.py`
