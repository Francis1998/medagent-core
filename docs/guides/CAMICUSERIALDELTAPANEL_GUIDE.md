# CamIcuSerialDeltaPanel Guide

![CamIcuSerialDeltaPanel](../../assets/cam_icu_serial_delta_panel_demo.gif)

Research-only Safety #297 serial delta panel.
Offline helper.
Gap vs MDCalc / CAM-ICU delirium serial delta-trend panel. Distinct from `CamIcuDeliriumScorer` / `FourAtSerialDeltaPanel`.

Stack: **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.cam_icu_serial_delta_panel import (
    CamIcuSerialDeltaFactors,
    CamIcuSerialDeltaPanel,
)

findings = CamIcuSerialDeltaPanel().check(CamIcuSerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
