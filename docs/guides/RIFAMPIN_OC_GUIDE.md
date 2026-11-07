# Rifampin + Oral Contraceptive Efficacy Guide

![Rifampin + OC demo](../../assets/rifampin_oc_demo.gif)

Research-only advisory checker for GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro summarization.

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
