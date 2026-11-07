"""HL7 CDS Hooks 2.0 services over medagent's deterministic medication-safety checks.

Transport-independent core of the ``/cds-services`` API (see
``medagent.api.cds_hooks``): service discovery, request and feedback
validation, and the FHIR → screening → cards pipeline, which reuses the MCP
``parse_fhir_bundle`` and ``screen_medications`` tools. Deterministic, offline
and RESEARCH USE ONLY.
"""

from medagent.cds_hooks.engine import INDICATOR_BY_SEVERITY, HookResult, evaluate_hook
from medagent.cds_hooks.requests import (
    CdsHooksRequestError,
    FeedbackItem,
    HookRequest,
    parse_feedback,
    parse_hook_request,
)
from medagent.cds_hooks.services import (
    PREFETCH_TEMPLATES,
    SERVICES,
    SERVICES_BY_ID,
    CdsService,
    discovery_document,
)

__all__ = [
    "INDICATOR_BY_SEVERITY",
    "PREFETCH_TEMPLATES",
    "SERVICES",
    "SERVICES_BY_ID",
    "CdsHooksRequestError",
    "CdsService",
    "FeedbackItem",
    "HookRequest",
    "HookResult",
    "discovery_document",
    "evaluate_hook",
    "parse_feedback",
    "parse_hook_request",
]
