# Cha2ds2VascSerialDeltaPanel Guide

![Cha2ds2VascSerialDeltaPanel](../../assets/cha2ds2_vasc_serial_delta_panel_demo.gif)

Research-only advisory panel (Safety #270).
Gap vs MDCalc / CHA2DS2-VASc serial delta-trend panel. Distinct from `Cha2ds2VascStrokeRiskScorer` / `HeartSerialDeltaPanel`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.cha2ds2_vasc_serial_delta_panel import (
    Cha2ds2VascSerialDeltaFactors,
    Cha2ds2VascSerialDeltaPanel,
)

findings = Cha2ds2VascSerialDeltaPanel().check(Cha2ds2VascSerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. No network I/O.
