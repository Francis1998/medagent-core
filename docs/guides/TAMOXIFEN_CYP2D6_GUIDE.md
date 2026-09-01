# Tamoxifen + Strong CYP2D6 Inhibitor Checker

![demo](../../assets/tamoxifen_cyp2d6_demo.gif)

`TamoxifenCyp2d6Checker` — Tamoxifen is a prodrug activated by CYP2D6 to endoxifen. Strong CYP2D6 inhibitors (fluoxetine, paroxetine, bupropion, quinidine) can reduce activation and undermine breast-cancer endocrine therapy. Distinct from generic SSRI panels and codeine CYP2D6 checks.

Findings are advisory `TamoxifenCyp2d6Risk` records — **RESEARCH USE ONLY**.
Prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 when summarizing.

## Usage

```python
from medagent.models import Medication
from medagent.safety import TamoxifenCyp2d6Checker

findings = TamoxifenCyp2d6Checker().check(
    [
        Medication(name="tamoxifen"),
        Medication(name="fluoxetine"),
    ]
)
```

## See also

- [SAFETY.md §3.113](../../SAFETY.md)
