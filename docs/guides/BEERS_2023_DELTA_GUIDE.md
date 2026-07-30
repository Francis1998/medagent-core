# Beers 2023 Criteria Update-Delta Checker Guide

*medagent-core — Safety Control #35*

![Beers 2023 delta checker flow](../../assets/beers_2023_delta_demo.gif)

## Overview

`Beers2023DeltaChecker` flags a conservative panel of **2023 AGS Beers
Criteria update deltas** — medications newly added or strengthened as
avoid/caution recommendations versus the prior Beers edition. It complements
`BeersCriteriaChecker` (Safety Control #15), which covers the classic
older-adult PIM catalog (benzodiazepines, tertiary TCAs, long-acting
sulfonylureas such as glyburide, first-generation antihistamines, and related
agents).

Findings are advisory `Beers2023DeltaRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`.

## Curated 2023 delta panel

| Delta kind | Agents / pairs | Typical severity |
|---|---|---|
| new_avoid | aspirin (primary prevention), warfarin (prefer DOAC initiation) | HIGH |
| expanded_avoid | glipizide, glimepiride (sulfonylurea class expansion) | HIGH |
| new_caution | rivaroxaban, dabigatran; duloxetine, venlafaxine, desvenlafaxine | MODERATE |
| concurrent_avoid | opioid × gabapentin / pregabalin | HIGH |

Matching is whole-token based: `Glipizidefree` and `Aspirinoid` are ignored,
while `Glipizide 5mg` and `Aspirin 81mg` match. The check applies only when
`age >= 65`. Aspirin findings are suppressed when `conditions` document
secondary prevention (for example CAD, MI, stent, stroke, or TIA). A single
medication entry naming both an opioid and a gabapentinoid is not treated as a
co-prescribed concurrent pair.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import Beers2023DeltaChecker

findings = Beers2023DeltaChecker().check(
    medications=[
        Medication(name="Glipizide 5mg daily"),
        Medication(name="Duloxetine 60mg"),
        Medication(name="Oxycodone 10mg BID"),
        Medication(name="Gabapentin 300mg TID"),
        Medication(name="Lisinopril 10mg"),
    ],
    age=72,
)
for finding in findings:
    print(
        finding.delta_kind,
        finding.agent,
        finding.agent_b,
        finding.severity,
        finding.update_summary,
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

- [SAFETY.md §3.35](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Classic Beers PIM panel: `safety/beers_criteria_checker.py` (Safety Control #15)
- STOPP/START: `safety/stopp_start_checker.py`
- Fall-risk medications: `safety/fall_risk_checker.py`
