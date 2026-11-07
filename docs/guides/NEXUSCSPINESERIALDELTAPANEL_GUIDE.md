# NexusCspineSerialDeltaPanel Guide

![NexusCspineSerialDeltaPanel](../../assets/nexus_cspine_serial_delta_panel_demo.gif)

Research-only serial delta panel (Safety #285).
Gap vs MDCalc / NEXUS C-spine serial delta-trend panel. Distinct from `NexusCspineScorer` / `CanadianCspineRuleScorer`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.nexus_cspine_serial_delta_panel import (
    NexusCspineSerialDeltaFactors,
    NexusCspineSerialDeltaPanel,
)

findings = NexusCspineSerialDeltaPanel().check(NexusCspineSerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Advisory. No network I/O. Never modifies medications.
