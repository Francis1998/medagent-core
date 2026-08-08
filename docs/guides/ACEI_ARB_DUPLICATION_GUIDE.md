# ACEI + ARB + ARNI Dual-Blockade Duplication Checker Guide

*medagent-core — Safety Control #50*

![ACEI ARB duplication checker flow](../../assets/acei_arb_duplication_demo.gif)

## Overview

`AceiArbDuplicationChecker` flags concurrent therapy across **≥2 distinct
RAAS classes** among ACE inhibitors, ARBs, and ARNIs — dual blockade that
increases hyperkalemia, hypotension, and renal risk without outcome benefit.
This check complements the triple-whammy (NSAID + ACEI/ARB + diuretic) checker
and generic drug-drug interaction flagging.

Findings are advisory `AceiArbDuplicationRisk` records — **RESEARCH USE ONLY**
— and the checker is exported from `medagent.safety`. Severity is **CRITICAL**
when ACEI + ARB are both present, and **HIGH** for ACEI/ARB + ARNI two-class
combinations without ACEI+ARB.

## ACEI panel

| Agent | Notes |
|---|---|
| lisinopril | ACE inhibitor |
| enalapril | ACE inhibitor |
| ramipril | ACE inhibitor |

## ARB panel

| Agent | Notes |
|---|---|
| losartan | angiotensin receptor blocker |
| valsartan | angiotensin receptor blocker |
| olmesartan | angiotensin receptor blocker |

## ARNI panel

| Agent | Notes |
|---|---|
| sacubitril | ARNI component (neprilysin inhibitor) |

Every cross-class agent pair yields one finding. Medication matching is
whole-token based. Same-class duplicates (e.g. two ACEIs) do not flag.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import AceiArbDuplicationChecker

findings = AceiArbDuplicationChecker().check(
    medications=[
        Medication(name="Lisinopril 10 mg daily"),
        Medication(name="Losartan 50 mg daily"),
    ],
)
for finding in findings:
    print(
        finding.agent_a,
        finding.class_a,
        finding.agent_b,
        finding.class_b,
        finding.severity,
        finding.rationale,
    )
```

## Reasoning stack notes

When this checker's findings are summarized by an upstream reasoning / routing
layer, prefer current frontier models for clinical prose:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## Suggested repo description / topics

**Description:** Research-only medical agent core with deterministic safety
checkers and modern LLM adapters (GPT-5.5, Claude Sonnet 4.6, Gemini 3.x,
Kimi K2).

**Topics:** `medical-ai`, `drug-safety`, `ace-inhibitor`, `agentic-ai`, `python`

## See also

- [SAFETY.md §3.50](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Triple whammy renal risk: `safety/triple_whammy_checker.py`
