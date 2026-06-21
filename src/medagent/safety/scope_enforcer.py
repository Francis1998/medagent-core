"""Scope enforcer — prevents out-of-scope queries from reaching the agent.

Enforces the hard constraint that the agent operates only within its
pre-approved tool list and approved query domain. Queries requesting
internet access, code execution, or non-medical topics are rejected
before any LLM call is made.
"""

from __future__ import annotations

import re

from medagent.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Scope definitions
# ---------------------------------------------------------------------------

_OUT_OF_SCOPE_PATTERNS: list[re.Pattern[str]] = [
    # Internet/browsing requests
    re.compile(r"\bbrowse\s+(the\s+)?internet\b", re.IGNORECASE),
    re.compile(r"\bsearch\s+(the\s+)?web\b", re.IGNORECASE),
    re.compile(r"\bvisit\s+https?://", re.IGNORECASE),
    re.compile(r"\bopen\s+https?://", re.IGNORECASE),
    # Code execution requests
    re.compile(r"\brun\s+(the\s+)?(code|script|program|command)\b", re.IGNORECASE),
    re.compile(r"\bexecute\s+(code|bash|python|shell)\b", re.IGNORECASE),
    re.compile(r"\bos\.system\b", re.IGNORECASE),
    re.compile(r"\bsubprocess\b", re.IGNORECASE),
    # Clearly non-medical domains
    re.compile(r"\b(write|generate)\s+(a\s+)?(poem|song|story|joke)\b", re.IGNORECASE),
    re.compile(r"\b(stock|crypto|bitcoin|forex)\s+(price|market|trading)\b", re.IGNORECASE),
]

_APPROVED_TOPICS: list[str] = [
    "differential diagnosis",
    "drug interaction",
    "clinical reasoning",
    "biomedical literature",
    "lab results",
    "symptoms",
    "medical history",
    "patient history",
    "medication",
    "diagnosis",
    "disease",
    "treatment options",  # describing options ≠ prescribing
    "evidence-based",
    "clinical decision",
]


class ScopeViolationError(ValueError):
    """Raised when a query falls outside the agent's approved scope."""


class ScopeEnforcer:
    """Validates queries against the approved clinical reasoning scope.

    Args:
        strict_mode: When True, also checks that the query contains at least
            one approved-topic keyword. Default is False (only blocks
            prohibited patterns).
    """

    def __init__(self, strict_mode: bool = False) -> None:
        self._strict_mode = strict_mode

    def check_query_in_scope(self, query: str) -> None:
        """Verify that a query is within the approved clinical scope.

        Args:
            query: The clinician's question or reasoning task.

        Raises:
            ScopeViolationError: When the query contains prohibited patterns
                or (in strict mode) lacks any approved-topic keyword.
        """
        for pattern in _OUT_OF_SCOPE_PATTERNS:
            match = pattern.search(query)
            if match:
                logger.warning(
                    "scope_violation",
                    pattern=pattern.pattern,
                    match=match.group(0),
                    query_prefix=query[:100],
                )
                raise ScopeViolationError(
                    f"Query contains prohibited content: '{match.group(0)}'. "
                    "The medagent agent is restricted to clinical reasoning tasks only."
                )

        if self._strict_mode:
            query_lower = query.lower()
            has_approved_topic = any(topic in query_lower for topic in _APPROVED_TOPICS)
            if not has_approved_topic:
                raise ScopeViolationError(
                    "Query does not appear to be related to clinical reasoning. "
                    "Please ask a biomedical or clinical decision support question."
                )

        logger.debug("scope_check_passed", query_prefix=query[:80])

    def sanitise_for_llm(self, text: str) -> str:
        """Strip known jailbreak and prompt-injection patterns from text.

        Args:
            text: Input text to sanitise before inclusion in an LLM prompt.

        Returns:
            Sanitised text with injection patterns removed.
        """
        # Remove common jailbreak markers
        jailbreak_patterns = [
            re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
            re.compile(r"forget\s+(your\s+)?(instructions?|training)", re.IGNORECASE),
            re.compile(r"you\s+are\s+now\s+(a|an)\s+\w+", re.IGNORECASE),
            re.compile(r"act\s+as\s+(if\s+you\s+are\s+)?a(n)?\s+\w+", re.IGNORECASE),
        ]
        for pattern in jailbreak_patterns:
            text = pattern.sub("[REDACTED]", text)
        return text
