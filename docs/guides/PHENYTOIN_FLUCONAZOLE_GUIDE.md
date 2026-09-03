# Phenytoin + Fluconazole CYP2C9 Inhibition Guide

![Phenytoin + Fluconazole demo](../../assets/phenytoin_fluconazole_demo.gif)

Research-only advisory checker for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 summarization.

## Why

Fluconazole inhibits CYP2C9, increasing phenytoin levels and toxicity risk
(nystagmus, ataxia, seizures).  Distinct from warfarin-azole and other
CYP2C9 interaction checkers.

## Usage

```python
from medagent.safety import PhenytoinFluconazoleChecker
from medagent.models import Medication

findings = PhenytoinFluconazoleChecker().check(
    [
        Medication(name="phenytoin"),
        Medication(name="fluconazole"),
    ]
)
```

## Safety

Advisory only; never auto-modifies medications. RESEARCH USE ONLY.
