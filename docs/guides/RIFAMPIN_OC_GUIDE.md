# Rifampin + Oral Contraceptive Efficacy Guide

![Rifampin + OC demo](../../assets/rifampin_oc_demo.gif)

Research-only advisory checker for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 summarization.

## Why

Rifampin is a potent CYP3A4 inducer that dramatically reduces oral
contraceptive efficacy, creating contraceptive failure risk.  Recommend
alternative or additional contraception when co-prescribed.

## Usage

```python
from medagent.safety import RifampinOcChecker
from medagent.models import Medication

findings = RifampinOcChecker().check(
    [
        Medication(name="rifampin"),
        Medication(name="ethinylestradiol"),
    ]
)
```

## Safety

Advisory only; never auto-modifies medications. RESEARCH USE ONLY.
