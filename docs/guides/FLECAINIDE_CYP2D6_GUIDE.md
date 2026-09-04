# Flecainide + Strong CYP2D6 Inhibitor Risk Guide

![Flecainide + Strong CYP2D6 Inhibitor Risk demo](../../assets/flecainide_cyp2d6_demo.gif)

Research-only advisory checker for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 summarization.

## Why

Flecainide is a CYP2D6 substrate; strong CYP2D6 inhibitors raise flecainide levels and proarrhythmia risk.

## Usage

```python
from medagent.safety import FlecainideCyp2d6Checker
from medagent.models import Medication

findings = FlecainideCyp2d6Checker().check(
    [
        Medication(name="flecainide"),
        Medication(name="fluoxetine"),
    ]
)
```

## Safety

Advisory only; never auto-modifies medications. RESEARCH USE ONLY.
