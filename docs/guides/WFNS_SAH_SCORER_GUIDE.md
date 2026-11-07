# WfnsSahScorer Guide

![WfnsSahScorer flow](../../assets/wfns_sah_demo.gif)

Research-only advisory scorer (Safety #208). Never modifies medications.

Gap vs MDCalc / AHA / EHR WFNS SAH grade. Distinct from `HuntHessSahScorer / NihssStrokeScorer`.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.wfns_sah_scorer import (
    WfnsSahFactors,
    WfnsSahScorer,
)

findings = WfnsSahScorer().check(WfnsSahFactors())
assert "RESEARCH USE ONLY" in findings[0].rationale
print(findings[0].band, findings[0].score)
```

## Safety

RESEARCH USE ONLY. See `SAFETY.md`.
