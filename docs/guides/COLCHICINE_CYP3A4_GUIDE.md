# Colchicine + Strong CYP3A4 Inhibitor Checker Guide

*medagent-core — Safety Control #81*

![Colchicine CYP3A4 checker flow](../../assets/colchicine_cyp3a4_demo.gif)

## Overview

`ColchicineCyp3a4Checker` flags colchicine-class therapy co-prescribed
with clarithromycin, ketoconazole, itraconazole, or ritonavir. Strong
CYP3A4 inhibition can markedly increase colchicine exposure and cause
severe or fatal toxicity.

Findings are advisory `ColchicineCyp3a4Risk` records —
**RESEARCH USE ONLY** — with **CRITICAL** severity. The checker is
exported from `medagent.safety`.

## Medication panels

| Class | Agents |
|---|---|
| Colchicine | colchicine, Colcrys, Mitigare, Gloperba |
| Strong CYP3A4 inhibitors | clarithromycin, ketoconazole, itraconazole, ritonavir |

Every unique colchicine × supported inhibitor pair across separate
medication entries yields one finding. Matching is whole-token based,
canonical pairs are de-duplicated, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import ColchicineCyp3a4Checker

findings = ColchicineCyp3a4Checker().check(
    [
        Medication(name="Colchicine 0.6 mg daily"),
        Medication(name="Clarithromycin 500 mg BID"),
    ]
)
```

## Scope boundaries

This focused panel is not an exhaustive interaction database and does
not replace renal/hepatic assessment, toxicity evaluation, or urgent
qualified clinical review. It never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.81](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Broad CYP3A4 control: `safety/statin_cyp3a4_checker.py`
