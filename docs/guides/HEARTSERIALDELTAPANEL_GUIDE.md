# HeartSerialDeltaPanel Guide

![HeartSerialDeltaPanel](../../assets/heart_serial_delta_panel_demo.gif)

Research-only advisory panel. Gap vs MDCalc / HEART serial delta-trend panel.
Distinct from `HeartScoreAcsScorer` / `MewsSerialDeltaPanel`.

Narrative polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.heart_serial_delta_panel import HeartSerialDeltaFactors, HeartSerialDeltaPanel

findings = HeartSerialDeltaPanel().check(HeartSerialDeltaFactors())
assert findings[0].rationale
```

## Safety

RESEARCH USE ONLY. Advisory. Never modifies medications. No network I/O.
