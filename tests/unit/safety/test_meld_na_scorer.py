"""Unit tests for MeldNaScorer."""

from __future__ import annotations

import pytest

from medagent.safety.meld_na_scorer import (
    MeldNaFactors,
    MeldNaScorer,
    compute_meld_na,
    meld_na_band,
)


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = MeldNaScorer().check(MeldNaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_elevated_band() -> None:
    """Multiple factors elevate band."""

    findings = MeldNaScorer().check(
        MeldNaFactors(
            bilirubin_ge_2=1, inr_ge_1_5=1, creatinine_ge_1_5=1, sodium_lt_135=1, dialysis=1
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        MeldNaScorer().check(MeldNaFactors(bilirubin_ge_2=2))


def test_all_five_abnormal_flags_are_not_low_risk() -> None:
    """Bilirubin >= 2, INR >= 1.5, dialysis and Na < 135 imply a MELD-Na of at least 28.

    The OPTN MELD-Na (Kim 2008, PMID 18768945) of the mildest labs consistent with
    every flag (bilirubin 2.0 mg/dL, INR 1.5, creatinine 4.0 for dialysis, Na 135)
    is 28, which Wiesner 2003 (PMID 12512033) places far above the low band.
    """
    findings = MeldNaScorer().check(
        MeldNaFactors(
            bilirubin_ge_2=1, inr_ge_1_5=1, creatinine_ge_1_5=1, sodium_lt_135=1, dialysis=1
        )
    )
    assert findings[0].band == "high"
    assert findings[0].score >= 20


@pytest.mark.parametrize(
    ("labs", "dialysis", "meld", "meld_na", "band"),
    [
        # Normal labs are floored at 1.0 and Na capped at 137: the MELD minimum of 6.
        ((0.8, 1.0, 0.9, 140.0), 0, 6, 6, "low"),
        # MELD(i) 2.262 -> 23; Na 129 adds 1.32*8 - 0.033*23*8 = 4.488 -> 27.
        ((2.5, 1.8, 1.9, 129.0), 0, 23, 27, "high"),
        # MELD(i) 1.093 -> 11: the sodium term needs MELD(i) > 11, so Na 125 adds nothing.
        ((1.0, 1.0, 1.6, 125.0), 0, 11, 11, "intermediate"),
        # MELD(i) 1.151 -> 12: now Na 125 applies, 12 + 15.84 - 4.752 = 23.088 -> 23.
        ((1.0, 1.0, 1.7, 125.0), 0, 12, 23, "high"),
        # Dialysis sets creatinine to 4.0 whatever was measured: 0.957*ln(4) + 0.643 -> 20.
        ((1.0, 1.0, 0.8, 137.0), 1, 20, 20, "high"),
        # Capped at 40.
        ((30.0, 5.0, 4.0, 120.0), 0, 40, 40, "high"),
    ],
)
def test_raw_labs_give_the_optn_meld_na(
    labs: tuple[float, float, float, float], dialysis: int, meld: int, meld_na: int, band: str
) -> None:
    bilirubin, inr, creatinine, sodium = labs
    computed = compute_meld_na(
        bilirubin_mg_dl=bilirubin,
        inr=inr,
        creatinine_mg_dl=creatinine,
        sodium_mmol_l=sodium,
        dialysis=bool(dialysis),
    )
    assert (computed.meld, computed.meld_na) == (meld, meld_na)
    findings = MeldNaScorer().check(
        MeldNaFactors(
            bilirubin_mg_dl=bilirubin,
            inr=inr,
            creatinine_mg_dl=creatinine,
            sodium_mmol_l=sodium,
            dialysis=dialysis,
        )
    )
    assert (findings[0].score, findings[0].band) == (meld_na, band)
    assert "raw labs" in findings[0].rationale


@pytest.mark.parametrize(
    ("meld_na", "band"), [(9, "low"), (10, "intermediate"), (19, "intermediate"), (20, "high")]
)
def test_wiesner_band_boundaries(meld_na: int, band: str) -> None:
    assert meld_na_band(meld_na)[0] == band


def test_flags_only_report_a_lower_bound() -> None:
    findings = MeldNaScorer().check(MeldNaFactors(bilirubin_ge_2=1))
    assert findings[0].score == 9
    assert "lower bound" in findings[0].rationale


@pytest.mark.parametrize(
    ("factors", "message"),
    [
        (MeldNaFactors(bilirubin_mg_dl=2.0, inr=1.2), "supplied together"),
        (
            MeldNaFactors(
                bilirubin_ge_2=1,
                bilirubin_mg_dl=2.0,
                inr=1.2,
                creatinine_mg_dl=1.0,
                sodium_mmol_l=137.0,
            ),
            "not both",
        ),
        (
            MeldNaFactors(bilirubin_mg_dl=0.0, inr=1.2, creatinine_mg_dl=1.0, sodium_mmol_l=137.0),
            "bilirubin_mg_dl must be a positive number",
        ),
    ],
)
def test_invalid_lab_combinations_raise(factors: MeldNaFactors, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        MeldNaScorer().check(factors)
