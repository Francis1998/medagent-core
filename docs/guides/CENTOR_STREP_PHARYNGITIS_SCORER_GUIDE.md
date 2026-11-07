# CentorStrepPharyngitisScorer Guide

![CentorStrepPharyngitisScorer](../../assets/centor_strep_pharyngitis_demo.gif)

Research-only advisory clinical score. Never modifies medications.

Prefer **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro** for narratives.

Distinct from `Curb65PneumoniaScorer / AntibioticStewardshipChecker`.

## Usage

```python
from medagent.safety.centor_strep_pharyngitis_scorer import (
    CentorStrepPharyngitisFactors,
    CentorStrepPharyngitisScorer,
)

findings = CentorStrepPharyngitisScorer().check(CentorStrepPharyngitisFactors())
assert findings[0].rationale.startswith("RESEARCH USE ONLY")
```
