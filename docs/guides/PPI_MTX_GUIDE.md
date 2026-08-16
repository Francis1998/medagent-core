# PPI + Methotrexate Toxicity Checker Guide

*medagent-core — Safety Control #74*

![PPI methotrexate checker flow](../../assets/ppi_mtx_demo.gif)

## Overview

`PpiMtxChecker` flags methotrexate co-prescribed with omeprazole,
esomeprazole, pantoprazole, lansoprazole, or rabeprazole. PPIs may reduce
methotrexate clearance, increasing exposure and toxicity risk.

Findings are advisory `PpiMtxRisk` records — **RESEARCH USE ONLY** — with
**HIGH** severity. The checker is exported from `medagent.safety`.

## Medication panels

| Class | Agents |
|---|---|
| Antifolate | methotrexate |
| PPI | omeprazole, esomeprazole, pantoprazole, lansoprazole, rabeprazole |

Every unique methotrexate × PPI pair across separate medication entries yields
one finding. Matching is whole-token based, canonical pairs are de-duplicated,
and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import PpiMtxChecker

findings = PpiMtxChecker().check(
    [Medication(name="Methotrexate 15 mg weekly"), Medication(name="Omeprazole 20 mg")]
)
```

## Scope boundaries

This control is distinct from methotrexate + NSAID toxicity and clopidogrel +
PPI reduced-activation screening. It does not infer dose-specific risk or
change therapy; obtain qualified clinical review.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.74](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Methotrexate + NSAID: `safety/mtx_nsaid_checker.py`
