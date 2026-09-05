# Tacrolimus + Rifampin Induction Risk Guide

![Tacrolimus + Rifampin Induction Risk demo](../../assets/tacrolimus_rifampin_demo.gif)

Research-only advisory checker for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 summarization.

## Why

Rifampin strongly induces CYP3A4, markedly reducing tacrolimus exposure and raising transplant rejection risk.

## Usage

```python
from medagent.safety import TacrolimusRifampinChecker
from medagent.models import Medication

findings = TacrolimusRifampinChecker().check(
    [
        Medication(name="tacrolimus"),
        Medication(name="rifampin"),
    ]
)
```

## Safety

Advisory only; never auto-modifies medications. RESEARCH USE ONLY.
