# Statin + Macrolide CYP3A4 Interaction Checker Guide

*medagent-core — Safety Control #67*

![Statin macrolide checker flow](../../assets/statin_macrolide_demo.gif)

## Overview

`StatinMacrolideChecker` flags a CYP3A4-metabolized statin co-prescribed with
a strong CYP3A4-inhibiting macrolide. Concurrent therapy increases myopathy and
rhabdomyolysis risk.

Findings are advisory `StatinMacrolideRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`. Severity is **CRITICAL**
for simvastatin/lovastatin and **HIGH** for atorvastatin.

## Statin panel

| Severity | Agents |
|---|---|
| CRITICAL | simvastatin, lovastatin |
| HIGH | atorvastatin |

## Macrolide partners

| Agents |
|---|
| clarithromycin, erythromycin |

Azithromycin is intentionally excluded as a weaker CYP3A4 inhibitor.

Every unique statin × macrolide pair across separate medication entries yields
one finding. Matching is whole-token based, duplicates are de-duplicated by
canonical pair, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import StatinMacrolideChecker

findings = StatinMacrolideChecker().check(
    medications=[
        Medication(name="Simvastatin 40 mg nightly"),
        Medication(name="Clarithromycin 500 mg BID"),
    ],
)
for finding in findings:
    print(
        finding.agent,
        finding.partner_agent,
        finding.severity,
        finding.rationale,
    )
```

## Scope boundaries

This control targets the focused statin × strong macrolide CYP3A4 pair.
Broader statin + strong CYP3A4 inhibitor screening (azoles, ritonavir,
grapefruit) belongs to `StatinCyp3a4Checker`. This control does not replace
qualified clinical review, and it never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.67](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Broader statin CYP3A4 panel: `safety/statin_cyp3a4_checker.py`
