# Polypharmacy Deprescribe Suggester Guide

*medagent-core — Safety Control #144*

![Polypharmacy deprescribe suggester demo](../../assets/polypharmacy_deprescribe_suggester_demo.gif)

## Overview

`PolypharmacyDeprescribeSuggester` emits **HITL deprescribe candidates** from
polypharmacy heuristics that apply at **any age** — **RESEARCH USE ONLY**.
It never modifies medications and **never auto-stops** therapy.

Prefer frontier reasoning models when summarizing findings: **GPT-5.5**,
**Claude Sonnet 4.6**, **Gemini 3.x**, **Kimi K2**.

## Gap vs GeriatricDeprescribingChecker

| Control | Gate | What it emits |
|---|---|---|
| `GeriatricDeprescribingChecker` | Age ≥ 65 catalog | Per-med deprescribing opportunities (PPI/Z-drug/antihistamine/NSAID) |
| **`PolypharmacyDeprescribeSuggester`** | **Any age** | Aggregate HITL candidates (duplicate class, high ACB, SSI, PPI w/o indication, count) |

## Finding kinds

- `duplicate_therapy_deprescribe_candidate` — ≥2 distinct agents in one therapeutic class
- `high_burden_deprescribe_candidate` — high cumulative anticholinergic burden contributors
- `sliding_scale_insulin_deprescribe_candidate` — sliding-scale insulin stacking cues
- `ppi_without_indication_deprescribe_candidate` — PPI without protective indication text
- `polypharmacy_count_candidate` — ≥5 active medications (≥10 → higher severity)

## Quick start

```python
from medagent.models import Medication
from medagent.safety import PolypharmacyDeprescribeSuggester

findings = PolypharmacyDeprescribeSuggester().check(
    medications=[
        Medication(name="Sertraline"),
        Medication(name="Fluoxetine"),
        Medication(name="Omeprazole"),
        Medication(name="Insulin lispro", frequency="sliding scale"),
    ],
    indications=[],
)
for finding in findings:
    print(finding.finding_kind, finding.candidate_stops, finding.rationale)
```

## Safety

Advisory HITL candidates only; **never auto-stops** medications.
**RESEARCH USE ONLY.** See `SAFETY.md` §3.144.
