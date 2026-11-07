# DukeEndocarditisCriteriaScorer Guide

![DukeEndocarditisCriteriaScorer demo](../../assets/duke-endocarditis_demo.gif)

Research-only advisory scorer. Never modifies medications. Never network I/O.
Closes gaps vs MDCalc / AHA modified Duke endocarditis criteria.

Optional narrative via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.duke_endocarditis_criteria_scorer import (
    DukeEndocarditisCriteriaFactors,
    DukeEndocarditisCriteriaScorer,
)

findings = DukeEndocarditisCriteriaScorer().check(DukeEndocarditisCriteriaFactors())
assert "RESEARCH USE ONLY" in findings[0].rationale
```

## Safety

See `SAFETY.md` §3.224. Humans decide therapy.
