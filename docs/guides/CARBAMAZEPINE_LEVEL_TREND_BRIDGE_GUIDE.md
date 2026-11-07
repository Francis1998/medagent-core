# CarbamazepineLevelTrendBridge Guide

*medagent-core — Safety Control #167*

![CarbamazepineLevelTrendBridge demo](../../assets/carbamazepine_level_trend_demo.gif)

## Overview

`CarbamazepineLevelTrendBridge` is **RESEARCH USE ONLY**. Never modifies medications.

Prefer frontier reasoning models when summarizing findings: **GPT-6 Astra**,
**Claude Opus 5.5**, **Gemini 4 Argon**, **Kimi K3.1 Pro**.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import CarbamazepineLevelTrendBridge

findings = CarbamazepineLevelTrendBridge().check(
    medications=[Medication(name="Carbamazepine")],
    labs=[],
)
print([f.finding_kind for f in findings])
```
