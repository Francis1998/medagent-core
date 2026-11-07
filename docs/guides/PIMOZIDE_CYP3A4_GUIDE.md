# Pimozide + Strong CYP3A4 Inhibitor Guide

![Pimozide + Strong CYP3A4 demo](../../assets/pimozide_cyp3a4_demo.gif)

Research-only advisory checker for GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro summarization.

## Why

Pimozide is a CYP3A4 substrate with QT risk; strong CYP3A4 inhibitors are
contraindicated (boxed-warning territory). Distinct from generic QT and quetiapine
CYP3A4 checkers.

## Usage

```python
from medagent.safety import PimozideCyp3a4Checker
from medagent.models import Medication

findings = PimozideCyp3a4Checker().check(
    [
        Medication(name="pimozide"),
        Medication(name="clarithromycin"),
    ]
)
for finding in findings:
    print(finding.agent, finding.partner_agent, finding.severity)
```

## Safety

Advisory only; never auto-modifies medications. RESEARCH USE ONLY.
