# News2SerialDeltaPanel Guide

![News2SerialDeltaPanel](../../assets/news2_serial_delta_panel_demo.gif)

Research-only advisory scorer.
Gap vs MDCalc / NEWS2 serial delta-trend panel. Distinct from `News2EarlyWarningScorer` / `SofaOrganFailureScorer`.

Optional narrative via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.news2_serial_delta_panel import News2SerialDeltaFactors, News2SerialDeltaPanel

findings = News2SerialDeltaPanel().check(News2SerialDeltaFactors())
assert findings[0].rationale
```

## Safety

RESEARCH USE ONLY. Never modifies medications. No network I/O.
