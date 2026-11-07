# PrismIiiPediatricScorer Guide

![PrismIiiPediatricScorer demo](../../assets/prism-iii-pediatric_demo.gif)

Research-only advisory scorer. Never modifies medications. Gap vs MDCalc / PICU PRISM III pediatric ICU score.

Optional narrative via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `PewsEarlyWarningScorer / ApacheIiLiteScorer`.

## Usage

```python
from medagent.safety.prism_iii_pediatric_scorer import (
    PrismIiiPediatricFactors,
    PrismIiiPediatricScorer,
)

findings = PrismIiiPediatricScorer().check(PrismIiiPediatricFactors())
print(findings[0].band, findings[0].rationale)
```
