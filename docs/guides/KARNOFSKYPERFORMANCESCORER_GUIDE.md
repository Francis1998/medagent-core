# KarnofskyPerformanceScorer Guide

![KarnofskyPerformanceScorer](../../assets/karnofsky_performance_scorer_demo.gif)

Research-only advisory scorer.
Gap vs MDCalc / Karnofsky Performance Status screen. Distinct from `EcogPerformanceScorer` / `BarthelAdlScorer`.

Optional narrative via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.karnofsky_performance_scorer import (
    KarnofskyPerformanceFactors,
    KarnofskyPerformanceScorer,
)

findings = KarnofskyPerformanceScorer().check(KarnofskyPerformanceFactors())
assert findings[0].rationale
```

## Safety

RESEARCH USE ONLY. Never modifies medications. No network I/O.
