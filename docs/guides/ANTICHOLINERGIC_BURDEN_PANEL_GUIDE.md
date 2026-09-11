# Anticholinergic Burden Panel Guide

*medagent-core — Safety Control #142*

![Anticholinergic burden panel demo](../../assets/anticholinergic_burden_panel_demo.gif)

## Overview

`AnticholinergicBurdenPanel` aggregates **anticholinergic cognitive burden
(ACB)** agents into panel-level `AnticholinergicBurdenPanelRisk` findings —
**RESEARCH USE ONLY**. Never modifies medications.

Prefer frontier reasoning models when summarizing findings: **GPT-5.5**,
**Claude Sonnet 4.6**, **Gemini 3.x**, **Kimi K2**.

## Gap vs existing checker

| Control | What it emits |
|---|---|
| `AnticholinergicBurdenChecker` | Per-medication ACB score + cumulative total |
| **`AnticholinergicBurdenPanel`** | Aggregate panel findings by `finding_kind` |

## Finding kinds

- `acb_threshold_exceeded` — total ACB ≥ 3 (clinically significant threshold)
- `high_acb_burden` — high cumulative load (total ≥ 5, or ≥ 3 with ≥ 2 agents)
- `multi_strong_anticholinergic_stack` — ≥ 2 strong (score-3) agents

## Quick start

```python
from medagent.models import Medication
from medagent.safety import AnticholinergicBurdenPanel

findings = AnticholinergicBurdenPanel().check(
    medications=[
        Medication(name="Amitriptyline"),
        Medication(name="Oxybutynin"),
        Medication(name="Diphenhydramine"),
    ],
)
for finding in findings:
    print(finding.finding_kind, finding.total_acb_score, finding.rationale)
```

## Safety

Advisory only; never auto-modifies medications.
**RESEARCH USE ONLY.** See `SAFETY.md` §3.142.
