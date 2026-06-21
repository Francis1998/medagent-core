"""Tests for MedicalOutputValidator."""

from __future__ import annotations

import pytest

from medagent.llm.validator import MedicalOutputValidationError, MedicalOutputValidator


@pytest.fixture()
def validator() -> MedicalOutputValidator:
    """Return a MedicalOutputValidator instance for testing."""
    return MedicalOutputValidator()


class TestMedicalOutputValidator:
    """Tests for LLM output validation."""

    def test_valid_content_passes(self, validator: MedicalOutputValidator) -> None:
        """Standard non-prohibited content must pass validation."""
        validator.validate(
            "The differential includes Type 2 Diabetes mellitus as a top hypothesis."
        )

    def test_empty_content_fails(self, validator: MedicalOutputValidator) -> None:
        """Empty string must fail validation."""
        with pytest.raises(MedicalOutputValidationError, match="too short"):
            validator.validate("")

    def test_short_content_fails(self, validator: MedicalOutputValidator) -> None:
        """Content shorter than 10 chars must fail validation."""
        with pytest.raises(MedicalOutputValidationError):
            validator.validate("ok")

    def test_prescribe_keyword_rejected(self, validator: MedicalOutputValidator) -> None:
        """Content containing 'prescribe' must fail."""
        with pytest.raises(MedicalOutputValidationError, match="prohibited"):
            validator.validate("I would prescribe metformin 500mg for this patient.")

    def test_start_patient_on_rejected(self, validator: MedicalOutputValidator) -> None:
        """'Start the patient on' phrasing must be rejected."""
        with pytest.raises(MedicalOutputValidationError):
            validator.validate("You should start the patient on lisinopril immediately.")

    def test_administer_dosage_rejected(self, validator: MedicalOutputValidator) -> None:
        """'Administer X mg' language must be rejected."""
        with pytest.raises(MedicalOutputValidationError):
            validator.validate("Administer 10 mg of furosemide intravenously.")

    def test_validate_json_parses_valid_json(self, validator: MedicalOutputValidator) -> None:
        """validate_json must successfully parse a valid JSON dict."""
        content = '{"hypotheses": [], "confidence": 0.8}'
        result = validator.validate_json(content, required_keys=["hypotheses"])
        assert "hypotheses" in result

    def test_validate_json_strips_markdown_fences(
        self, validator: MedicalOutputValidator
    ) -> None:
        """JSON wrapped in markdown code fences must be parsed correctly."""
        content = '```json\n{"hypotheses": [{"label": "T2DM"}]}\n```'
        result = validator.validate_json(content, required_keys=["hypotheses"])
        assert result["hypotheses"][0]["label"] == "T2DM"  # type: ignore[index]

    def test_validate_json_missing_key_raises(self, validator: MedicalOutputValidator) -> None:
        """Missing required keys must raise MedicalOutputValidationError."""
        content = '{"hypotheses": []}'
        with pytest.raises(MedicalOutputValidationError, match="missing required keys"):
            validator.validate_json(content, required_keys=["hypotheses", "confidence"])

    def test_validate_json_invalid_json_raises(self, validator: MedicalOutputValidator) -> None:
        """Invalid JSON must raise MedicalOutputValidationError."""
        with pytest.raises(MedicalOutputValidationError, match="not valid JSON"):
            validator.validate_json("this is not JSON at all", required_keys=[])
