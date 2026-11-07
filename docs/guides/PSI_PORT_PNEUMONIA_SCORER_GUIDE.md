# PsiPortPneumoniaScorer Guide

![PsiPortPneumoniaScorer](../../assets/psi_port_pneumonia_demo.gif)

Research-only advisory clinical score (Safety #182). Never modifies medications.

Prefer **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro** for narratives.

Distinct from `Curb65PneumoniaScorer / SofaOrganFailureScorer`.

## Usage

```python
from medagent.safety.psi_port_pneumonia_scorer import PsiPortFactors, PsiPortPneumoniaScorer

findings = PsiPortPneumoniaScorer().check(PsiPortFactors())
assert findings[0].rationale.startswith("RESEARCH USE ONLY")
```
