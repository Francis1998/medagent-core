"""Tests for the FHIR bundle parser."""

from __future__ import annotations

from typing import Any

import pytest

from medagent.extraction.fhir_parser import (
    FHIRParseError,
    parse_fhir_bundle,
    sanitise_clinical_text,
)


@pytest.fixture()
def minimal_fhir_bundle() -> dict[str, Any]:
    """Return a minimal valid FHIR R4 Bundle for testing."""
    return {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "patient-001",
                    "identifier": [{"value": "MRN-12345"}],
                    "birthDate": "1980-06-15",
                    "gender": "male",
                }
            },
            {
                "resource": {
                    "resourceType": "Condition",
                    "code": {
                        "coding": [{"display": "Type 2 diabetes mellitus"}],
                        "text": "Type 2 diabetes mellitus",
                    },
                }
            },
            {
                "resource": {
                    "resourceType": "MedicationRequest",
                    "medicationCodeableConcept": {
                        "text": "Metformin",
                        "coding": [
                            {
                                "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                                "code": "6809",
                            }
                        ],
                    },
                    "dosageInstruction": [{"text": "500mg twice daily"}],
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "code": {"text": "HbA1c"},
                    "valueQuantity": {"value": 7.8, "unit": "%"},
                    "referenceRange": [{"low": {"value": 4.0}, "high": {"value": 5.6}}],
                    "interpretation": [{"coding": [{"code": "H"}]}],
                }
            },
        ],
    }


class TestParseFhirBundle:
    """Tests for parse_fhir_bundle."""

    def test_parses_valid_bundle(self, minimal_fhir_bundle: dict[str, Any]) -> None:
        """A valid FHIR bundle must be parsed without raising."""
        ctx = parse_fhir_bundle(minimal_fhir_bundle, pii_salt="test-salt")
        assert ctx.patient_id_hash is not None
        assert len(ctx.patient_id_hash) == 64

    def test_patient_id_hashed(self, minimal_fhir_bundle: dict[str, Any]) -> None:
        """The patient MRN must not appear literally in the patient_id_hash."""
        ctx = parse_fhir_bundle(minimal_fhir_bundle, pii_salt="test-salt")
        assert "MRN-12345" not in ctx.patient_id_hash

    def test_age_computed_from_birthdate(self, minimal_fhir_bundle: dict[str, Any]) -> None:
        """Age must be computed from birthDate and be a plausible integer."""
        ctx = parse_fhir_bundle(minimal_fhir_bundle, pii_salt="test-salt")
        assert ctx.age is not None
        assert 30 <= ctx.age <= 70  # born 1980, checked ~2025

    def test_age_accounts_for_birthday_not_yet_reached(self) -> None:
        """Age must not be overstated when this year's birthday has not occurred."""
        from datetime import date

        today = date.today()
        birth_year = today.year - 40
        # Birthday on Dec 31: not yet reached on any day except Dec 31 itself.
        bundle: dict[str, Any] = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "p-age",
                        "birthDate": f"{birth_year}-12-31",
                    }
                }
            ],
        }
        expected = 40 if (today.month, today.day) >= (12, 31) else 39
        ctx = parse_fhir_bundle(bundle, pii_salt="test-salt")
        assert ctx.age == expected

    def test_age_partial_year_month_birthdate_accounts_for_month(self) -> None:
        """A ``YYYY-MM`` birthDate must use its month for the birthday check.

        FHIR ``birthDate`` may be a partial ``YYYY-MM`` date. The month-not-yet-
        reached adjustment previously ran only for full ``YYYY-MM-DD`` dates, so
        a partial date whose birth month is later in the year overstated age by
        one year.
        """
        from datetime import date

        today = date.today()
        birth_year = today.year - 30

        def _bundle(birth_date: str) -> dict[str, Any]:
            return {
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Patient",
                            "id": "p-partial",
                            "birthDate": birth_date,
                        }
                    }
                ],
            }

        if today.month < 12:
            later_month = f"{birth_year}-{today.month + 1:02d}"
            ctx = parse_fhir_bundle(_bundle(later_month), pii_salt="test-salt")
            assert ctx.age == 29
        if today.month > 1:
            earlier_month = f"{birth_year}-{today.month - 1:02d}"
            ctx = parse_fhir_bundle(_bundle(earlier_month), pii_salt="test-salt")
            assert ctx.age == 30

    def test_sex_extracted(self, minimal_fhir_bundle: dict[str, Any]) -> None:
        """Sex field must be extracted from the Patient resource."""
        ctx = parse_fhir_bundle(minimal_fhir_bundle, pii_salt="test-salt")
        assert ctx.sex == "male"

    def test_diagnoses_extracted(self, minimal_fhir_bundle: dict[str, Any]) -> None:
        """Condition text must be included in diagnoses_history."""
        ctx = parse_fhir_bundle(minimal_fhir_bundle, pii_salt="test-salt")
        assert any("diabetes" in d.lower() for d in ctx.diagnoses_history)

    def test_medications_extracted(self, minimal_fhir_bundle: dict[str, Any]) -> None:
        """MedicationRequest must be parsed into Medication objects."""
        ctx = parse_fhir_bundle(minimal_fhir_bundle, pii_salt="test-salt")
        assert len(ctx.medications) >= 1
        assert any(m.name == "Metformin" for m in ctx.medications)

    def test_lab_results_extracted(self, minimal_fhir_bundle: dict[str, Any]) -> None:
        """Observation must be parsed into LabResult with abnormal=True."""
        ctx = parse_fhir_bundle(minimal_fhir_bundle, pii_salt="test-salt")
        assert len(ctx.lab_results) >= 1
        hba1c = next(
            (lab_result for lab_result in ctx.lab_results if lab_result.test_name == "HbA1c"),
            None,
        )
        assert hba1c is not None
        assert hba1c.abnormal is True

    def test_raw_fhir_preserved(self, minimal_fhir_bundle: dict[str, Any]) -> None:
        """raw_fhir must preserve the original bundle for audit."""
        ctx = parse_fhir_bundle(minimal_fhir_bundle, pii_salt="test-salt")
        assert ctx.raw_fhir is not None
        assert ctx.raw_fhir["resourceType"] == "Bundle"

    def test_invalid_resource_type_raises(self) -> None:
        """A non-Bundle resourceType must raise FHIRParseError."""
        with pytest.raises(FHIRParseError):
            parse_fhir_bundle({"resourceType": "Patient", "entry": []}, pii_salt="test-salt")

    def test_non_dict_input_raises(self) -> None:
        """A non-dict input must raise FHIRParseError."""
        with pytest.raises(FHIRParseError):
            parse_fhir_bundle("not a dict", pii_salt="test-salt")  # type: ignore[arg-type]


class TestSanitiseClinicalText:
    """Tests for PII redaction in clinical free text."""

    def test_redacts_date_pattern(self) -> None:
        """DOB date patterns must be replaced with [REDACTED-DOB]."""
        result = sanitise_clinical_text("DOB: 06/15/1980")
        assert "06/15/1980" not in result
        assert "REDACTED" in result

    def test_redacts_iso_and_named_month_dob_formats(self) -> None:
        """ISO-8601 and DD-Mon-YYYY DOB dates must also be redacted.

        ``birthDate`` in FHIR is ISO-8601 (``YYYY-MM-DD``); the original numeric
        pattern only matched 1-2 digit leading components, so an ISO date (and a
        named-month ``DD-Mon-YYYY`` date) leaked through unredacted.
        """
        iso_result = sanitise_clinical_text("Patient DOB 2023-01-15 presented.")
        assert "2023-01-15" not in iso_result
        assert "[REDACTED-DOB]" in iso_result

        named_result = sanitise_clinical_text("Born 15-Jan-2020 in county.")
        assert "15-Jan-2020" not in named_result
        assert "[REDACTED-DOB]" in named_result

        # Clinical content adjacent to the date must be preserved.
        assert "presented" in iso_result

    def test_redacts_social_security_number(self) -> None:
        """SSN (NNN-NN-NNNN) must be redacted before text reaches an LLM.

        The de-identification contract lists SSN as PII, but no prior pattern
        matched the SSN 3-2-4 shape: the date patterns require 1-2 digit leading
        groups and the phone pattern requires a 3-digit middle group. An SSN
        therefore leaked through ``sanitise_clinical_text`` unredacted.
        """
        result = sanitise_clinical_text("Patient SSN 123-45-6789 on file.")
        assert "123-45-6789" not in result
        assert "[REDACTED-SSN]" in result
        # Adjacent clinical content must be preserved.
        assert "Patient" in result and "file" in result

    def test_redacts_phone_number(self) -> None:
        """Phone number patterns must be replaced with [REDACTED-PHONE]."""
        result = sanitise_clinical_text("Contact: 555-867-5309")
        assert "555-867-5309" not in result

    def test_redacts_parenthesized_area_code_phone(self) -> None:
        """A phone with a parenthesised area code must be redacted.

        The phone regex was anchored with a leading ``\\b`` and only accepted a
        bare 3-digit area code, so a common ``(415) 555-1234`` number (whose
        ``(`` is a non-word character with no preceding word boundary) leaked
        through ``sanitise_clinical_text`` unredacted into text passed to the
        LLM. Parenthesised and country-code-prefixed numbers must be redacted.
        """
        paren_result = sanitise_clinical_text("Call the clinic at (415) 555-1234 today.")
        assert "415" not in paren_result
        assert "555-1234" not in paren_result
        assert "[REDACTED-PHONE]" in paren_result

        country_result = sanitise_clinical_text("Reachable at +1 415-555-1234.")
        assert "415-555-1234" not in country_result
        assert "[REDACTED-PHONE]" in country_result

    def test_redacts_email(self) -> None:
        """Email addresses must be replaced with [REDACTED-EMAIL]."""
        result = sanitise_clinical_text("Email: patient@example.com")
        assert "patient@example.com" not in result

    def test_redacts_multi_label_email_domain_fully(self) -> None:
        """Subdomain / compound-TLD email domains must not leak a trailing fragment.

        The domain pattern previously matched only the first dotted label, so a
        subdomain (``mail.hospital.org``) or compound TLD (``acme.co.uk``) left a
        recognizable ``.org`` / ``.co.uk`` fragment revealing the organisation.
        """
        subdomain = sanitise_clinical_text("Contact john.doe@mail.hospital.org for records.")
        assert "[REDACTED-EMAIL]" in subdomain
        assert ".org" not in subdomain
        assert "hospital" not in subdomain

        compound_tld = sanitise_clinical_text("Email a@team.acme.co.uk please.")
        assert "[REDACTED-EMAIL]" in compound_tld
        assert ".co.uk" not in compound_tld
        assert "acme" not in compound_tld

    def test_preserves_clinical_content(self) -> None:
        """Clinical observations must not be redacted."""
        text = "Patient presents with elevated troponin and chest pain"
        result = sanitise_clinical_text(text)
        assert "troponin" in result
        assert "chest pain" in result
