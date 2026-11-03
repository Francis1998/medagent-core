# RassSerialDeltaPanel Guide

![RassSerialDeltaPanel](../../assets/rass_serial_delta_panel_demo.gif)

Research-only Safety #295 serial delta panel.
Offline helper.
Gap vs MDCalc / RASS sedation serial delta-trend panel. Distinct from `RassSedationScorer` / `CamIcuDeliriumScorer`.

Stack: **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.rass_serial_delta_panel import RassSerialDeltaFactors, RassSerialDeltaPanel

findings = RassSerialDeltaPanel().check(RassSerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
