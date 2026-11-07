# QSofaSepsisScreenScorer Guide

![QSofaSepsisScreenScorer](../../assets/qsofa_sepsis_screen_demo.gif)

Research-only advisory clinical score (Safety #178). Never modifies medications.

Prefer **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro** for narratives.

Distinct from `SofaOrganFailureScorer / VitalsTriageChecker`.

## Usage

```python
from medagent.safety.qsofa_sepsis_screen_scorer import (
    QSofaSepsisScreenFactors,
    QSofaSepsisScreenScorer,
)

findings = QSofaSepsisScreenScorer().check(QSofaSepsisScreenFactors())
assert findings[0].rationale.startswith("RESEARCH USE ONLY")
```
