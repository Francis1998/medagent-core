# MewsSerialDeltaPanel Guide

![MewsSerialDeltaPanel](../../assets/mews_serial_delta_panel_demo.gif)

Research-only advisory score (Safety #256).
Gap vs MDCalc / MEWS serial delta-trend panel. Distinct from `MewsScorer` / `News2SerialDeltaPanel`.

Optional narrative via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.mews_serial_delta_panel import (
    MewsSerialDeltaFactors,
    MewsSerialDeltaPanel,
)

findings = MewsSerialDeltaPanel().check(MewsSerialDeltaFactors())
assert findings[0].rationale
print(findings[0].band)
```

## Safety

RESEARCH USE ONLY. Advisory. Never modifies medications. No network I/O.
