# Apixaban + Strong CYP3A4/P-gp Inhibitor Guide

![Apixaban + Strong CYP3A4/P-gp demo](../../assets/apixaban_cyp3a4_demo.gif)

Research-only advisory checker for GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro summarization.

## Why

Apixaban is a CYP3A4/P-gp substrate; strong inhibitors (ketoconazole, itraconazole,
ritonavir) raise exposure and bleeding risk. Distinct from dabigatran P-gp and DOAC
inducer checkers.

## Usage

```python
from medagent.safety import ApixabanCyp3a4Checker
from medagent.models import Medication

findings = ApixabanCyp3a4Checker().check(
    [
        Medication(name="apixaban"),
        Medication(name="ketoconazole"),
    ]
)
for finding in findings:
    print(finding.agent, finding.partner_agent, finding.severity)
```

## Safety

Advisory only; never auto-modifies medications. RESEARCH USE ONLY.
