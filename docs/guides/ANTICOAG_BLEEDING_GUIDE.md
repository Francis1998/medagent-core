# Anticoagulation Bleeding-Risk Checker Guide

*medagent-core — Safety Control #33*

![Anticoagulation bleeding-risk checker flow](../../assets/anticoag_bleeding_demo.gif)

## Overview

`AnticoagBleedingChecker` flags a conservative panel of **anticoagulant ×
bleeding-risk augmenter** combinations — for example **warfarin + aspirin**,
**apixaban + clopidogrel**, or **rivaroxaban + ibuprofen**. It complements
duplicate-therapy anticoagulant detection and generic DDI screening by focusing
specifically on additive hemorrhagic mechanisms: anticoagulation layered on
platelet dysfunction (antiplatelets, SSRIs) or GI mucosal injury (NSAIDs).

Findings are advisory `AnticoagBleedingRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`.

## Curated panel

| Anticoagulants | Augmenter categories | Typical severity |
|---|---|---|
| warfarin, apixaban, rivaroxaban, dabigatran, enoxaparin, heparin | Antiplatelet: aspirin, clopidogrel, prasugrel, ticagrelor | CRITICAL |
| warfarin, apixaban, rivaroxaban, dabigatran, enoxaparin, heparin | NSAID: ibuprofen, naproxen, diclofenac, ketorolac, meloxicam, celecoxib, indomethacin | HIGH |
| warfarin, apixaban, rivaroxaban, dabigatran, enoxaparin, heparin | SSRI: sertraline, fluoxetine, paroxetine, citalopram, escitalopram, fluvoxamine | MODERATE |

Matching is whole-token based: `Pseudowarfarin` and `Aspirinoid` are ignored,
while `Warfarin 5mg` and `Aspirin 81mg` match. A combination requires two
distinct active medication entries — one descriptive string naming both agents is
not treated as co-prescribed therapy.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import AnticoagBleedingChecker

findings = AnticoagBleedingChecker().check(
    medications=[
        Medication(name="Warfarin 5mg daily"),
        Medication(name="Aspirin 81mg"),
        Medication(name="Sertraline 50mg"),
        Medication(name="Lisinopril 10mg"),
    ],
)
for finding in findings:
    print(
        finding.combination_id,
        finding.anticoagulant_agent,
        finding.augmenter_agent,
        finding.severity,
        finding.mechanism,
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

- [SAFETY.md §3.33](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Duplicate anticoagulant therapy: `safety/duplicate_therapy.py`
- Renal-dose DOAC checks: `safety/renal_dose_checker.py`
