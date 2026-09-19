# CyclosporineLevelTrendBridge Guide

*medagent-core — Safety Control #165*

![Cyclosporine level trend bridge demo](../../assets/cyclosporine_level_trend_demo.gif)

## Overview

`CyclosporineLevelTrendBridge` combines **cyclosporine** exposure with serial serum
cyclosporine levels showing rising, elevated, or clearly supratherapeutic
trends into advisory `CyclosporineLevelTrendAlert` findings — **RESEARCH USE ONLY**. Never
modifies medications.

Prefer frontier reasoning models when summarizing findings: **GPT-5.5**,
**Claude Sonnet 4.6**, **Gemini 3.x**, **Kimi K2**.

## Finding kinds

- `rising_cyclosporine_level`
- `elevated_cyclosporine_level`
- `supratherapeutic_cyclosporine_level`
- `cyclosporine_level_monitoring_advisory`

## Quick start

```python
from medagent.models import Medication
from medagent.safety import CyclosporineLevelTrendBridge

findings = CyclosporineLevelTrendBridge().check(
    medications=[Medication(name="Cyclosporine")],
    labs=[
        {"name": "serum cyclosporine", "value": 200.0, "drawn_at": "a"},
        {"name": "serum cyclosporine", "value": 500.0, "drawn_at": "b"},
    ],
)
print([f.finding_kind for f in findings])
```
