"""Safety module — disclaimer injector, PII hasher, scope enforcer."""

from medagent.safety.disclaimer import (
    ESCALATION_MESSAGE,
    MANDATORY_DISCLAIMER,
    MEDICAL_SYSTEM_PROMPT,
)
from medagent.safety.fall_risk_checker import FallRiskChecker
from medagent.safety.geriatric_deprescribing_checker import GeriatricDeprescribingChecker
from medagent.safety.lactation_checker import LactationSafetyChecker
from medagent.safety.pii_hasher import hash_pii, hash_pii_dict, redact_fhir_pii
from medagent.safety.pregnancy_lactation_checker import PregnancyLactationChecker
from medagent.safety.qtc_ddi_checker import QtcDdiChecker
from medagent.safety.qtc_monitoring_checker import QtcMonitoringChecker
from medagent.safety.scope_enforcer import ScopeEnforcer, ScopeViolationError
from medagent.safety.taper_schedule_checker import TaperScheduleChecker

__all__ = [
    "ESCALATION_MESSAGE",
    "MANDATORY_DISCLAIMER",
    "MEDICAL_SYSTEM_PROMPT",
    "FallRiskChecker",
    "GeriatricDeprescribingChecker",
    "LactationSafetyChecker",
    "PregnancyLactationChecker",
    "QtcDdiChecker",
    "QtcMonitoringChecker",
    "ScopeEnforcer",
    "ScopeViolationError",
    "TaperScheduleChecker",
    "hash_pii",
    "hash_pii_dict",
    "redact_fhir_pii",
]
