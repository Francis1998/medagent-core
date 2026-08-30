# Warfarin + Metronidazole INR/Bleeding Checker

*medagent-core — Safety Control #109*

![warfarin_metronidazole checker flow](../../assets/warfarin_metronidazole_demo.gif)

## Overview

`WarfarinMetronidazoleChecker` flags warfarin metronidazole co-prescription risks.
Metronidazole can inhibit CYP2C9-mediated warfarin metabolism, elevating INR
and bleeding risk.

Findings are advisory `WarfarinMetronidazoleRisk` records — **RESEARCH USE ONLY**.
Distinct from warfarin_nsaid, warfarin_tmpsmx, amio_warfarin, and
fluoroquinolone_warfarin interaction checkers.

## Medication panels

| Class | Agents | Severity |
|---|---|---|
| Primary | `warfarin` | — |
| Primary | `coumadin` | — |
| Primary | `jantoven` | — |
| Partner | `metronidazole` | `HIGH` |
| Partner | `flagyl` | `HIGH` |

## Quick start

```python
from medagent.models import Medication
from medagent.safety import WarfarinMetronidazoleChecker

findings = WarfarinMetronidazoleChecker().check(
    [Medication(name="warfarin"), Medication(name="metronidazole")]
)
```

## Reasoning stack notes

Prefer **GPT-5.5**, **Claude Sonnet 4.6**, **Gemini 3.x**, **Kimi K2**.

## See also

- [SAFETY.md §3.109](../../SAFETY.md)
