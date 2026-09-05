# Ethinylestradiol + Lamotrigine Level Reduction Risk Guide

![Ethinylestradiol + Lamotrigine Level Reduction Risk demo](../../assets/ethinylestradiol_lamotrigine_demo.gif)

Research-only advisory checker for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 summarization.

## Why

Ethinylestradiol-containing combined oral contraceptives induce UGT glucuronidation of lamotrigine, reducing levels and increasing seizure risk.

## Usage

```python
from medagent.safety import EthinylestradiolLamotrigineChecker
from medagent.models import Medication

findings = EthinylestradiolLamotrigineChecker().check(
    [
        Medication(name="lamotrigine"),
        Medication(name="ethinylestradiol"),
    ]
)
```

## Safety

Advisory only; never auto-modifies medications. RESEARCH USE ONLY.
