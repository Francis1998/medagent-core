# HeartSerialDeltaPanel Guide

![HeartSerialDeltaPanel](../../assets/heart_serial_delta_panel_demo.gif)

Research-only advisory panel. Gap vs MDCalc / HEART serial delta-trend panel.
Distinct from `HeartScoreAcsScorer` / `MewsSerialDeltaPanel`.

Narrative polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.heart_serial_delta_panel import HeartSerialDeltaFactors, HeartSerialDeltaPanel

findings = HeartSerialDeltaPanel().check(HeartSerialDeltaFactors())
assert findings[0].rationale
```

## Safety

RESEARCH USE ONLY. Advisory. Never modifies medications. No network I/O.
