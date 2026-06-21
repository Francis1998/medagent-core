"""PII field hashing for patient data de-identification.

All patient-identifying fields (name, DOB, MRN, SSN) are SHA-256 hashed
with a configurable salt before being stored or processed. The raw PII
values never leave the intake boundary.

The hash is deterministic so that the same patient always maps to the
same pseudonymous identifier, enabling audit log linkage without
re-identifying the patient.
"""

from __future__ import annotations

import hashlib
import hmac

from medagent.config import settings


def hash_pii(value: str, salt: str | None = None) -> str:
    """Hash a PII string with HMAC-SHA256 using the configured salt.

    Args:
        value: The raw PII value (e.g. patient MRN, name, DOB).
        salt: Optional override salt. Uses ``settings.pii_hash_salt`` when None.

    Returns:
        64-character lowercase hex digest.

    Example:
        >>> h = hash_pii("MRN-123456")
        >>> len(h)
        64
    """
    effective_salt = (salt or settings.pii_hash_salt).encode()
    return hmac.new(effective_salt, value.encode(), hashlib.sha256).hexdigest()


def hash_pii_dict(
    data: dict[str, str],
    pii_keys: set[str],
    salt: str | None = None,
) -> dict[str, str]:
    """Hash all PII keys in a flat dict, leaving non-PII keys unchanged.

    Args:
        data: Dict potentially containing PII values.
        pii_keys: Set of key names whose values should be hashed.
        salt: Optional override salt.

    Returns:
        New dict with PII values replaced by their hashes.

    Example:
        >>> result = hash_pii_dict({"mrn": "123", "age": "45"}, {"mrn"})
        >>> result["age"]
        '45'
        >>> len(result["mrn"])
        64
    """
    return {k: (hash_pii(v, salt=salt) if k in pii_keys else v) for k, v in data.items()}


def redact_fhir_pii(fhir_bundle: dict[str, object]) -> dict[str, object]:
    """Remove PII from a FHIR bundle before it is passed to an LLM.

    Removes Patient.name, Patient.birthDate, Patient.identifier, and
    Patient.telecom entries. Returns a new dict; does not mutate the input.

    Args:
        fhir_bundle: The raw FHIR R4 bundle dict.

    Returns:
        A copy of the bundle with PII fields removed.
    """
    import copy

    bundle = copy.deepcopy(fhir_bundle)
    entries = bundle.get("entry", [])
    if not isinstance(entries, list):
        return bundle

    for entry in entries:
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "Patient":
            for pii_field in ("name", "birthDate", "identifier", "telecom", "address"):
                resource.pop(pii_field, None)

    return bundle
