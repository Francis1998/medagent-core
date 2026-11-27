# MeldNaScorer Guide

![MeldNaScorer](../../assets/meld_na_demo.gif)

Research-only advisory scorer. Closes the MDCalc / AASLD / EHR MELD-Na score gap.

Optional later polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `ChildPughLiverSeverityScorer / SofaOrganFailureScorer`.

## Usage

```python
from medagent.safety.meld_na_scorer import (
    MeldNaScorer,
    MeldNaFactors,
)

findings = MeldNaScorer().check(
    MeldNaFactors(bilirubin_mg_dl=2.5, inr=1.8, creatinine_mg_dl=1.9, sodium_mmol_l=129)
)
print(findings[0].score, findings[0].band)  # 27 high
```

The score is the OPTN MELD-Na (Kim et al., N Engl J Med 2008, PMID 18768945): labs
below 1.0 are set to 1.0, creatinine is capped at 4.0 mg/dL (4.0 with `dialysis=1`),
sodium is bounded to 125-137 mmol/L and the result is capped at 40. Bands follow the
Wiesner 2003 3-month mortality strata: `low` < 10, `intermediate` 10-19, `high` >= 20.
The legacy 0/1 flags (`bilirubin_ge_2`, `inr_ge_1_5`, `creatinine_ge_1_5`,
`sodium_lt_135`) still work but only give the lowest MELD-Na consistent with them;
pass the raw labs for the exact score. With units and per-criterion derivations, use
the `meld_na` calculator ([Clinical calculators guide](CLINICAL_CALCULATORS_GUIDE.md)).

## Safety

RESEARCH USE ONLY. Never modifies medications. No HTTP. See `SAFETY.md` #194.
