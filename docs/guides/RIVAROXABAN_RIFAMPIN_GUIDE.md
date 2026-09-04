# Rivaroxaban + Rifampin Induction Risk Guide

![Rivaroxaban + Rifampin Induction Risk demo](../../assets/rivaroxaban_rifampin_demo.gif)

Research-only advisory checker for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 summarization.

## Why

Rifampin strongly induces CYP3A4 and P-gp, reducing rivaroxaban exposure and increasing thrombotic risk.

## Usage

```python
from medagent.safety import RivaroxabanRifampinChecker
from medagent.models import Medication

findings = RivaroxabanRifampinChecker().check(
    [
        Medication(name="rivaroxaban"),
        Medication(name="rifampin"),
    ]
)
```

## Safety

Advisory only; never auto-modifies medications. RESEARCH USE ONLY.
