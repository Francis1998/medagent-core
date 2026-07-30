# INR / TTR Monitoring Cadence Checker Guide

*medagent-core — Safety Control #34*

![INR/TTR monitoring checker flow](../../assets/inr_ttr_demo.gif)

## Overview

`InrTtrChecker` flags when **INR monitoring is missing or overdue**, or when
**time in therapeutic range (TTR) is below a quality threshold**, for patients
on warfarin / vitamin K antagonist (VKA) therapy. It complements
`AnticoagBleedingChecker` (anticoagulant × bleeding-risk augmenter pairs) and
the lab critical-value INR panic panel by focusing on monitoring cadence and
anticoagulation control quality — a gap versus clinic INR/TTR surveillance
workflows.

Findings are advisory `InrTtrRisk` records — **RESEARCH USE ONLY** — and the
checker is exported from `medagent.safety`. Direct oral anticoagulants (DOACs)
are intentionally out of scope.

## Monitoring thresholds

| Phase / metric | Threshold | When applied |
|---|---|---|
| Initiation INR | ≤ **7 days** | `on_initiation=True` (therapy start or dose titration) |
| Maintenance INR | ≤ **28 days** | default (`on_initiation=False`) |
| TTR quality | ≥ **65%** (default) | `ttr_percent` provided and below threshold |

An `overdue_inr` finding is emitted when `last_inr_days_ago` is
**unknown/missing** or **exceeds** the interval for the active phase. A
`low_ttr` finding is emitted only when `ttr_percent` is known and strictly
below the threshold (`None` does not imply low TTR).

## Curated VKA panel

| Category | Agents / aliases | Typical overdue severity |
|---|---|---|
| Vitamin K antagonist | warfarin (aliases: coumadin, jantoven), acenocoumarol, phenprocoumon | HIGH (CRITICAL on initiation) |

Medication matching is whole-token based: `Pseudowarfarin` does not match
`warfarin`. TTR &lt;50% elevates `low_ttr` severity to CRITICAL.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import InrTtrChecker

findings = InrTtrChecker().check(
    medications=[
        Medication(name="Warfarin 5mg daily"),
        Medication(name="Apixaban 5mg BID"),  # DOAC — ignored
    ],
    last_inr_days_ago=40,
    ttr_percent=58.0,
    on_initiation=False,
)
for finding in findings:
    print(
        finding.agent,
        finding.finding_kind,
        finding.severity,
        finding.recommended_interval_days,
        finding.ttr_percent,
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

- [SAFETY.md §3.34](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Anticoagulation bleeding-risk: `safety/anticoag_bleeding_checker.py`
- Lab critical INR values: `safety/lab_critical_value_checker.py`
