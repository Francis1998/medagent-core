# FourScoreSerialDeltaPanel Guide

![FourScoreSerialDeltaPanel](../../assets/four_score_serial_delta_panel_demo.gif)

Research-only Safety #289 serial delta panel.
Gap vs MDCalc / FOUR Score serial delta-trend panel. Distinct from `FourScoreScorer` / `GcsSerialDeltaPanel`.

Stack: **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.four_score_serial_delta_panel import (
    FourScoreSerialDeltaFactors,
    FourScoreSerialDeltaPanel,
)

findings = FourScoreSerialDeltaPanel().check(FourScoreSerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies therapy. No network I/O.
