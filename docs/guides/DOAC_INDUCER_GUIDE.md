# DOAC + Strong Inducer Thrombosis-Risk Checker

*medagent-core — Safety Control #97*

![DOAC inducer checker flow](../../assets/doac_inducer_demo.gif)

## Overview

`DoacInducerChecker` flags DOAC therapy (apixaban/Eliquis, rivaroxaban/Xarelto, edoxaban/Savaysa, dabigatran/Pradaxa) co-prescribed with strong CYP3A4/P-gp inducers. Rifampin/rifampicin is `CRITICAL`; carbamazepine/Tegretol, phenytoin/Dilantin, and St John's wort / hypericum are `HIGH`. Strong induction can reduce anticoagulant exposure and increase thrombosis risk.

Findings are advisory `DoacInducerRisk` records — **RESEARCH USE ONLY**. The checker is exported from `medagent.safety`. This DOAC-focused inducer control is distinct from warfarin interaction checkers and from DOAC + NSAID / antiplatelet bleeding controls.

## Medication panels

| Class | Agents | Severity |
|---|---|---|
| DOAC | apixaban, eliquis, rivaroxaban, xarelto, edoxaban, savaysa, dabigatran, pradaxa | — |
| Strong inducer | rifampin, rifampicin | `CRITICAL` |
| Strong inducer | carbamazepine, tegretol, phenytoin, dilantin, st johns wort, st john's wort, hypericum | `HIGH` |

Every unique supported pair across separate medication entries yields one finding. Matching is whole-token/whole-alias based, canonical pairs are de-duplicated, and output ordering is deterministic (severity-first, then medication name).

## Quick start

```python
from medagent.models import Medication
from medagent.safety import DoacInducerChecker

findings = DoacInducerChecker().check(
    [
        Medication(name="Apixaban 5 mg BID"),
        Medication(name="Rifampin 600 mg daily"),
    ]
)
```

## Scope boundaries

This is a **DOAC-focused inducer** control, distinct from warfarin interaction checkers (`warfarin_azole_checker.py`, `amio_warfarin_checker.py`) and from DOAC bleeding intensifiers (`doac_nsaid_checker.py`, `doac_antiplatelet_checker.py`). Weaker inducers remain out of scope. The control does not replace anticoagulation stewardship or qualified clinical review, and never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.97](../../SAFETY.md)
- [README safety controls table](../../README.md)
- DOAC + NSAID: `safety/doac_nsaid_checker.py`
- DOAC + antiplatelet: `safety/doac_antiplatelet_checker.py`
- Generic interaction validation: `retrieval/drug_sources.py`
