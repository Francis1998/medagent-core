# LinezolidPlateletTrendBridge Guide

*medagent-core — Safety Control #168*

![LinezolidPlateletTrendBridge demo](../../assets/linezolid_platelet_trend_demo.gif)

## Overview

`LinezolidPlateletTrendBridge` is **RESEARCH USE ONLY**. Never modifies medications.

Prefer frontier reasoning models when summarizing findings: **GPT-5.5**,
**Claude Sonnet 4.6**, **Gemini 3.x**, **Kimi K2**.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import LinezolidPlateletTrendBridge

findings = LinezolidPlateletTrendBridge().check(
    medications=[Medication(name="Linezolid")],
    labs=[],
)
print([f.finding_kind for f in findings])
```
