"""Medical output validator.

Validates LLM completions for:
1. JSON structure compliance (for structured task outputs).
2. Presence of prohibited content (direct prescriptions, specific dosages).
3. Minimum content requirements (non-empty, plausible length).

All medical outputs must pass validation before being returned by the router.
"""

from __future__ import annotations

import json
import re

from medagent.logging_config import get_logger

logger = get_logger(__name__)

# Patterns that indicate a direct prescription — prohibited by the system
_PROHIBITED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bprescribe\b", re.IGNORECASE),
    re.compile(r"\bstart\s+the\s+patient\s+on\b", re.IGNORECASE),
    re.compile(r"\badminister\s+\d+\s*mg\b", re.IGNORECASE),
    re.compile(r"\bdosage\s+of\s+\d+\s*mg\b", re.IGNORECASE),
    re.compile(r"\brecommend\s+\d+\s*mg\b", re.IGNORECASE),
]

_MIN_CONTENT_LENGTH = 10
_MAX_CONTENT_LENGTH = 50_000


class MedicalOutputValidationError(ValueError):
    """Raised when an LLM output fails medical safety validation."""


class MedicalOutputValidator:
    """Validates LLM completions against the medagent medical output schema.

    Validation is intentionally strict: a failure here triggers the fallback
    adapter chain rather than surfacing a potentially unsafe response.
    """

    def validate(self, content: str) -> None:
        """Validate an LLM completion string.

        Args:
            content: Raw text returned by an LLM adapter.

        Raises:
            MedicalOutputValidationError: When the content violates any rule.
        """
        self._check_length(content)
        self._check_prohibited_patterns(content)

    def validate_json(self, content: str, required_keys: list[str]) -> dict[str, object]:
        """Validate that content is valid JSON with required top-level keys.

        Args:
            content: LLM completion expected to be JSON.
            required_keys: Keys that must be present in the top-level dict.

        Returns:
            Parsed JSON dict.

        Raises:
            MedicalOutputValidationError: On parse failure or missing keys.
        """
        self.validate(content)

        # Strip markdown fences
        clean = re.sub(r"```(?:json)?", "", content).strip().rstrip("`").strip()

        try:
            data = json.loads(clean)
        except json.JSONDecodeError as exc:
            raise MedicalOutputValidationError(f"LLM output is not valid JSON: {exc}") from exc

        if not isinstance(data, dict):
            raise MedicalOutputValidationError("LLM output JSON must be an object")

        missing = [k for k in required_keys if k not in data]
        if missing:
            raise MedicalOutputValidationError(f"LLM output missing required keys: {missing}")

        return data  # type: ignore[return-value]

    def _check_length(self, content: str) -> None:
        """Ensure the content is non-empty and within bounds."""
        if len(content) < _MIN_CONTENT_LENGTH:
            raise MedicalOutputValidationError(
                f"LLM output too short: {len(content)} chars (min {_MIN_CONTENT_LENGTH})"
            )
        if len(content) > _MAX_CONTENT_LENGTH:
            raise MedicalOutputValidationError(
                f"LLM output suspiciously long: {len(content)} chars (max {_MAX_CONTENT_LENGTH})"
            )

    def _check_prohibited_patterns(self, content: str) -> None:
        """Reject outputs containing direct prescription language."""
        for pattern in _PROHIBITED_PATTERNS:
            match = pattern.search(content)
            if match:
                logger.warning(
                    "prohibited_content_detected",
                    pattern=pattern.pattern,
                    match=match.group(0),
                )
                raise MedicalOutputValidationError(
                    f"LLM output contains prohibited prescription language: "
                    f"'{match.group(0)}' matched pattern '{pattern.pattern}'"
                )
