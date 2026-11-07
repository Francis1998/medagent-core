# AlvaradoAppendicitisScorer Guide

![AlvaradoAppendicitisScorer](../../assets/alvarado_appendicitis_demo.gif)

Research-only Alvarado appendicitis score. Never modifies medications.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `OttawaAnkleRuleScorer` and `CentorStrepPharyngitisScorer`.

## Usage

```python
from medagent.safety.alvarado_appendicitis_scorer import (
    AlvaradoAppendicitisFactors,
    AlvaradoAppendicitisScorer,
)

findings = AlvaradoAppendicitisScorer().check(
    AlvaradoAppendicitisFactors(rlq_tenderness=1, leukocytosis=1)
)
assert findings[0].rationale.startswith("RESEARCH USE ONLY")
print(findings[0].band, findings[0].score)
```
