# MaddreyDiscriminantScorer Guide

![MaddreyDiscriminantScorer demo](../../assets/maddrey-discriminant_demo.gif)

Research-only advisory scorer. Never modifies medications. Gap vs MDCalc Maddrey discriminant function for alcoholic hepatitis.

Optional narrative via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

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
