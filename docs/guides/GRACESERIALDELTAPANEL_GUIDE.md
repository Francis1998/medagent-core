# GraceSerialDeltaPanel Guide

![GraceSerialDeltaPanel](../../assets/grace_serial_delta_panel_demo.gif)

Research-only Safety #282 serial delta panel.
Gap vs MDCalc / GRACE ACS serial delta-trend panel. Distinct from `GraceAcsScorer` / `HeartSerialDeltaPanel`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.grace_serial_delta_panel import GraceSerialDeltaFactors, GraceSerialDeltaPanel

findings = GraceSerialDeltaPanel().check(GraceSerialDeltaFactors())
print(findings[0].band)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. No network I/O.
