# EcogPerformanceScorer Guide

![EcogPerformanceScorer](../../assets/ecog_performance_scorer_demo.gif)

Research-only advisory scorer. Gap vs MDCalc / ECOG/WHO performance status screen.
Distinct from `GcsNeurologicStatusScorer` / `ApacheIiLiteScorer`. Safety #248.

Narrative polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.ecog_performance_scorer import EcogPerformanceFactors, EcogPerformanceScorer

findings = EcogPerformanceScorer().check(EcogPerformanceFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. No network I/O.
