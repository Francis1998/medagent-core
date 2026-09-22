"""Unit tests for ChildPughLiverSeverityScorer."""

from __future__ import annotations

import pytest

from medagent.models import Severity
from medagent.safety.child_pugh_liver_severity_scorer import (
    ChildPughFactors,
    ChildPughLiverSeverityScorer,
)


def test_class_a() -> None:
    findings = ChildPughLiverSeverityScorer().check(ChildPughFactors())
    assert findings[0].score == 5
    assert findings[0].child_class == "A"
    assert findings[0].severity == Severity.LOW


def test_class_c() -> None:
    findings = ChildPughLiverSeverityScorer().check(
        ChildPughFactors(
            bilirubin_points=3,
            albumin_points=3,
            inr_points=3,
            ascites_points=3,
            encephalopathy_points=3,
        )
    )
    assert findings[0].score == 15
    assert findings[0].child_class == "C"
    assert findings[0].band == "severe"


def test_invalid_points() -> None:
    with pytest.raises(ValueError, match="bilirubin_points"):
        ChildPughLiverSeverityScorer().check(ChildPughFactors(bilirubin_points=4))
