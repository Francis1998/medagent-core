# Sofosbuvir + Amiodarone Bradycardia Risk Guide

![Sofosbuvir + Amiodarone Bradycardia Risk demo](../../assets/sofosbuvir_amiodarone_demo.gif)

Research-only advisory checker for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 summarization.

## Why

Coadministration of sofosbuvir-containing HCV regimens with amiodarone can cause serious symptomatic bradycardia.

## Usage

```python
from medagent.safety import SofosbuvirAmiodaroneChecker
from medagent.models import Medication

findings = SofosbuvirAmiodaroneChecker().check(
    [
        Medication(name="sofosbuvir"),
        Medication(name="amiodarone"),
    ]
)
```

## Safety

Advisory only; never auto-modifies medications. RESEARCH USE ONLY.
