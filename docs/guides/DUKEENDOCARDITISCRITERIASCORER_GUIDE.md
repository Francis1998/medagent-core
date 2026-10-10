# DukeEndocarditisCriteriaScorer Guide

![DukeEndocarditisCriteriaScorer demo](../../assets/duke-endocarditis_demo.gif)

Research-only advisory scorer. Never modifies medications. Never network I/O.
Closes gaps vs MDCalc / AHA modified Duke endocarditis criteria.

Optional narrative via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

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
