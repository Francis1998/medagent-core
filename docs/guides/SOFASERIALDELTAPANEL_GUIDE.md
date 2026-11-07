# SofaSerialDeltaPanel Guide

![SofaSerialDeltaPanel](../../assets/sofa_serial_delta_panel_demo.gif)

Research-only advisory serial-delta panel. Gap vs MDCalc / SOFA serial delta-trend panel.
Distinct from `SofaOrganFailureScorer` / `News2SerialDeltaPanel`.

Optional narrative via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.sofa_serial_delta_panel import (
    SofaSerialDeltaFactors,
    SofaSerialDeltaPanel,
)

findings = SofaSerialDeltaPanel().check(
    SofaSerialDeltaFactors(prior_sofa_elevated=1, current_sofa_rise=1)
)
assert findings[0].rationale
print(findings[0].band, findings[0].score)
```

## Safety

RESEARCH USE ONLY. Advisory score. Never modifies medications. No network I/O.
