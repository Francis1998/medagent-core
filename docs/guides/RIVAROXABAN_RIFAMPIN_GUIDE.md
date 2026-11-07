# Rivaroxaban + Rifampin Induction Risk Guide

![Rivaroxaban + Rifampin Induction Risk demo](../../assets/rivaroxaban_rifampin_demo.gif)

Research-only advisory checker for GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro summarization.

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
for finding in findings:
    print(finding.agent, finding.partner_agent, finding.severity)
```

## Safety

Advisory only; never auto-modifies medications. RESEARCH USE ONLY.
