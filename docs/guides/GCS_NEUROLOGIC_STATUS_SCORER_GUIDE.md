# GcsNeurologicStatusScorer Guide

![GcsNeurologicStatusScorer](../../assets/gcs_neurologic_status_demo.gif)

Research-only advisory clinical score. Never modifies medications.

Prefer **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro** for narratives.

Distinct from `HeartScoreAcsScorer / VitalsTriageChecker`.

## Usage

```python
from medagent.safety.gcs_neurologic_status_scorer import (
    GcsNeurologicStatusFactors,
    GcsNeurologicStatusScorer,
)

findings = GcsNeurologicStatusScorer().check(GcsNeurologicStatusFactors())
assert findings[0].rationale.startswith("RESEARCH USE ONLY")
```
