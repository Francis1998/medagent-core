# PesiPeSeverityScorer Guide

![PesiPeSeverityScorer](../../assets/pesi_pe_severity_demo.gif)

Research-only advisory scorer. Closes the MDCalc / ESC / EHR PESI PE severity score gap.

Optional later polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `WellsPeProbabilityScorer` / `RevisedGenevaPeScorer`.

## Usage

```python
from medagent.safety.pesi_pe_severity_scorer import (
    PesiPeSeverityScorer,
    PesiPeSeverityFactors,
)

findings = PesiPeSeverityScorer().check(PesiPeSeverityFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. No HTTP. See `SAFETY.md` #199.
