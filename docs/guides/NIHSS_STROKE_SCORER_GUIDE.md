# NihssStrokeScorer Guide

![NihssStrokeScorer](../../assets/nihss_stroke_demo.gif)

Research-only advisory clinical score. Never modifies medications.
Closes MDCalc / AHA / EHR NIHSS stroke severity gaps.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `Cha2ds2VascStrokeRiskScorer / FallRiskChecker`.

## Usage

```python
from medagent.safety.nihss_stroke_scorer import NihssStrokeScorer, NihssFactors

findings = NihssStrokeScorer().check(NihssFactors())
print(findings[0].band, findings[0].score)
```
