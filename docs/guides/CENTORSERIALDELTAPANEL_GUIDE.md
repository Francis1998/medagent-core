# CentorSerialDeltaPanel Guide

![CentorSerialDeltaPanel](../../assets/centor_serial_delta_panel_demo.gif)

Research-only advisory panel (Safety #271).
Gap vs MDCalc / Centor serial delta-trend panel. Distinct from `CentorStrepPharyngitisScorer` / `HeartSerialDeltaPanel`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.centor_serial_delta_panel import (
    CentorSerialDeltaFactors,
    CentorSerialDeltaPanel,
)

findings = CentorSerialDeltaPanel().check(CentorSerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. No network I/O.
