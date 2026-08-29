# Tacrolimus + Strong CYP3A4 Inhibitor Exposure Checker

*medagent-core — Safety Control #104*

![tacrolimus_cyp3a4 checker flow](../../assets/tacrolimus_cyp3a4_demo.gif)

## Overview

`TacrolimusCyp3a4Checker` flags tacrolimus CYP3A4 co-prescription risks.
Strong CYP3A4 inhibition can markedly elevate tacrolimus exposure
and intensify nephrotoxicity / neurotoxicity risk.

Findings are advisory `TacrolimusCyp3a4Risk` records — **RESEARCH USE ONLY**.
The checker is exported from `medagent.safety`.
Distinct from cyclosporine interaction screens and general CYP3A4
checkers (colchicine/fentanyl/quetiapine).

## Medication panels

| Class | Agents | Severity |
|---|---|---|
| Primary | `tacrolimus` | — |
| Primary | `prograf` | — |
| Primary | `envarsus` | — |
| Primary | `astagraf` | — |
| Partner | `ketoconazole` | `CRITICAL` |
| Partner | `itraconazole` | `CRITICAL` |
| Partner | `clarithromycin` | `CRITICAL` |
| Partner | `ritonavir` | `CRITICAL` |
| Partner | `cobicistat` | `CRITICAL` |

## Quick start

```python
from medagent.models import Medication
from medagent.safety import TacrolimusCyp3a4Checker

findings = TacrolimusCyp3a4Checker().check(
    [
        Medication(name="tacrolimus"),
        Medication(name="ketoconazole"),
    ]
)
```

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.104](../../SAFETY.md)
- [README safety controls table](../../README.md)
