# Renal Dose Adjuster Guide

*medagent-core — Safety Control #131*

![Renal dose adjuster flow](../../assets/renal_dose_adjuster_demo.gif)

## Overview

`RenalDoseAdjuster` emits **banded educational regimen suggestions** for a
curated renally cleared panel when eGFR is known. Each advisory
`RenalDoseAdjustment` includes `band_label`, `suggested_regimen`, and
`rationale` — **RESEARCH USE ONLY**.

Prefer frontier reasoning models when summarizing findings: **GPT-5.5**,
**Claude Sonnet 4.6**, **Gemini 3.x**, **Kimi K2**.

## Gap vs RenalDoseChecker

`RenalDoseChecker` only emits **avoid** / **reduce dose** flags at eGFR
thresholds. This adjuster adds concrete **banded regimen cues** (for example
gabapentin eGFR 30–59 → divided-dose educational suggestion).

## Curated panel (examples)

| Agent | Example band | Educational regimen cue |
|---|---|---|
| gabapentin | egfr_30_59 | 200–700 mg/day in divided doses |
| metformin | egfr_lt_30 | generally avoid below eGFR 30 |
| pregabalin | egfr_le_30 | 25–75 mg once daily |
| allopurinol | egfr_le_30 | start ≤50–100 mg daily |
| enoxaparin | egfr_lt_30 | therapeutic 1 mg/kg once daily cue |

## Quick start

```python
from medagent.models import Medication
from medagent.safety import RenalDoseAdjuster

findings = RenalDoseAdjuster().check(
    medications=[Medication(name="Gabapentin 300mg")],
    egfr=45.0,
)
for finding in findings:
    print(finding.band_label, finding.suggested_regimen, finding.rationale)
```

## Safety

Advisory only; never auto-modifies medications or writes prescriptions.
**RESEARCH USE ONLY.**
