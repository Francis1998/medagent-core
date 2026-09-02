# Ergotamine / DHE + Strong CYP3A4 Inhibitor Guide

![Ergotamine + Strong CYP3A4 demo](../../assets/ergotamine_cyp3a4_demo.gif)

Research-only advisory checker for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 summarization.

## Why

Ergot alkaloids are CYP3A4 substrates; strong inhibitors can cause ergot
toxicity/vasospasm (contraindicated). Distinct from other CYP3A4 exposure checkers.

## Usage

```python
from medagent.safety import ErgotamineCyp3a4Checker
from medagent.models import Medication

findings = ErgotamineCyp3a4Checker().check(
    [
        Medication(name="ergotamine"),
        Medication(name="clarithromycin"),
    ]
)
```

## Safety

Advisory only; never auto-modifies medications. RESEARCH USE ONLY.
