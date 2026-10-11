# MaddreyDiscriminantScorer Guide

![MaddreyDiscriminantScorer demo](../../assets/maddrey-discriminant_demo.gif)

Research-only advisory scorer. Never modifies medications. Gap vs MDCalc Maddrey discriminant function for alcoholic hepatitis.

Optional narrative via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

Distinct from `MeldNaScorer / ChildPughLiverSeverityScorer`.

## Usage

```python
from medagent.safety.maddrey_discriminant_scorer import (
    MaddreyDiscriminantFactors,
    MaddreyDiscriminantScorer,
)

findings = MaddreyDiscriminantScorer().check(MaddreyDiscriminantFactors())
print(findings[0].band, findings[0].rationale)
```
