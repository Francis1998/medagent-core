# MeldNaScorer Guide

![MeldNaScorer](../../assets/meld_na_demo.gif)

Research-only advisory scorer. Closes the MDCalc / AASLD / EHR MELD-Na score gap.

Optional later polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `ChildPughLiverSeverityScorer / SofaOrganFailureScorer`.

## Usage

```python
from medagent.safety.meld_na_scorer import (
    MeldNaScorer,
    MeldNaFactors,
)

findings = MeldNaScorer().check(MeldNaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. No HTTP. See `SAFETY.md` #194.
