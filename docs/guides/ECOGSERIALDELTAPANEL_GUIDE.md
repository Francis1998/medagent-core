# EcogSerialDeltaPanel Guide

![EcogSerialDeltaPanel](../../assets/ecog_serial_delta_panel_demo.gif)

Research-only Safety #294 serial delta panel.
Gap vs MDCalc / ECOG performance serial delta-trend panel. Distinct from `EcogPerformanceScorer` / `KarnofskyPerformanceScorer`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.ecog_serial_delta_panel import EcogSerialDeltaFactors, EcogSerialDeltaPanel

findings = EcogSerialDeltaPanel().check(EcogSerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies therapy. No network I/O.
