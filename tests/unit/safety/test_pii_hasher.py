"""Tests for PII hashing utilities."""

from __future__ import annotations

from medagent.safety.pii_hasher import hash_pii, hash_pii_dict, redact_fhir_pii


class TestHashPii:
    """Tests for the hash_pii function."""

    def test_returns_64_char_hex(self) -> None:
        """hash_pii must return a 64-character lowercase hex string."""
        result = hash_pii("MRN-123456")
        assert len(result) == 64
        assert result == result.lower()
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self) -> None:
        """The same value and salt must always produce the same hash."""
        h1 = hash_pii("patient-001", salt="test-salt")
        h2 = hash_pii("patient-001", salt="test-salt")
        assert h1 == h2

    def test_different_values_different_hashes(self) -> None:
        """Different PII values must produce different hashes."""
        h1 = hash_pii("patient-001")
        h2 = hash_pii("patient-002")
        assert h1 != h2

    def test_different_salts_different_hashes(self) -> None:
        """The same value with different salts must produce different hashes."""
        h1 = hash_pii("patient-001", salt="salt-a")
        h2 = hash_pii("patient-001", salt="salt-b")
        assert h1 != h2

    def test_empty_string_hashes(self) -> None:
        """Empty string must still produce a valid 64-char hash."""
        result = hash_pii("")
        assert len(result) == 64


class TestHashPiiDict:
    """Tests for hash_pii_dict function."""

    def test_hashes_only_pii_keys(self) -> None:
        """Only keys in pii_keys should be hashed; others remain unchanged."""
        data = {"mrn": "123456", "age": "45", "name": "John"}
        result = hash_pii_dict(data, pii_keys={"mrn", "name"})
        assert result["age"] == "45"
        assert len(result["mrn"]) == 64
        assert len(result["name"]) == 64

    def test_missing_pii_key_not_added(self) -> None:
        """Keys in pii_keys that are not in data must not be added to result."""
        data = {"age": "45"}
        result = hash_pii_dict(data, pii_keys={"mrn"})
        assert "mrn" not in result
        assert result["age"] == "45"


class TestRedactFhirPii:
    """Tests for FHIR bundle PII redaction."""

    def test_removes_patient_name(self) -> None:
        """Patient name must be removed from the bundle."""
        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "name": [{"text": "John Doe"}],
                        "id": "p001",
                    }
                }
            ],
        }
        result = redact_fhir_pii(bundle)
        patient = result["entry"][0]["resource"]  # type: ignore[index]
        assert "name" not in patient

    def test_does_not_mutate_input(self) -> None:
        """The original bundle must not be mutated."""
        bundle: dict[str, object] = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "name": [{"text": "Jane Doe"}],
                    }
                }
            ],
        }
        _ = redact_fhir_pii(bundle)
        assert "name" in bundle["entry"][0]["resource"]  # type: ignore[index]

    def test_non_patient_resources_untouched(self) -> None:
        """Non-Patient resources must not be modified."""
        bundle: dict[str, object] = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Observation",
                        "code": {"text": "Hemoglobin"},
                    }
                }
            ],
        }
        result = redact_fhir_pii(bundle)
        obs = result["entry"][0]["resource"]  # type: ignore[index]
        assert obs["code"]["text"] == "Hemoglobin"  # type: ignore[index]

    def test_non_list_entries_return_bundle(self) -> None:
        """A malformed non-list entry field must return a copied bundle."""
        bundle: dict[str, object] = {"resourceType": "Bundle", "entry": "not-a-list"}

        result = redact_fhir_pii(bundle)

        assert result == bundle
        assert result is not bundle
