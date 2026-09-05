# Sirolimus + Strong CYP3A4 Inhibitor Risk Guide

![Sirolimus + Strong CYP3A4 Inhibitor Risk demo](../../assets/sirolimus_strong_cyp3a4_demo.gif)

Research-only advisory checker for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 summarization.

## Why

Sirolimus is a CYP3A4/P-gp substrate; strong CYP3A4 inhibitors raise sirolimus levels and toxicity risk.

## Usage

```python
from medagent.safety import SirolimusStrongCyp3a4Checker
from medagent.models import Medication

findings = SirolimusStrongCyp3a4Checker().check(
    [
        Medication(name="sirolimus"),
        Medication(name="ketoconazole"),
    ]
)
```

## Safety

Advisory only; never auto-modifies medications. RESEARCH USE ONLY.
