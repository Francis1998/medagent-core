"""Screen one patient against structured trial definitions (research use only).

:func:`screen_trials` validates the arguments against the published schema,
parses each trial definition, extracts de-identified patient facts through the
MCP FHIR path, evaluates every criterion and ranks the trials. The result is
shared by the MCP tool ``screen_trial_eligibility`` and ``POST
/trials/eligibility``; it carries the mandatory disclaimer, never claims
eligibility or enrollment, and its audit events hold hashes, ids and counts only.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from medagent.logging_config import get_logger
from medagent.mcp.schema import validate
from medagent.safety.disclaimer import MANDATORY_DISCLAIMER
from medagent.safety.pii_hasher import hash_pii
from medagent.trials.criteria import TrialInputError, parse_as_of, parse_trials
from medagent.trials.evaluator import RankedTrial, evaluate_trial, rank_trials
from medagent.trials.facts import PatientFacts, extract_patient_facts
from medagent.trials.schema import SCREEN_INPUT_SCHEMA, TRIAL_STATUSES

logger = get_logger(__name__)

MAX_REPORTED_PROBLEMS = 20

COVERAGE_NOTE = (
    "Research pre-screen only: medagent does not determine eligibility and never enrolls, "
    "contacts or refers anyone. Statuses come from a structured encoding of each trial that "
    "may be incomplete and from a partial, de-identified record; free-text criteria are never "
    "interpreted. The study team must verify every criterion against the full protocol and "
    "the patient's chart."
)


def canonical_json(value: Any) -> str:
    """Serialise ``value`` deterministically, as the MCP audit log does before hashing."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _has_lone_surrogate(value: Any) -> bool:
    """True when any string or key in ``value`` cannot be encoded as UTF-8."""
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
        elif isinstance(item, str):
            try:
                item.encode("utf-8")
            except UnicodeEncodeError:
                return True
    return False


@dataclass(frozen=True)
class TrialScreening:
    """The ranked pre-screening result for one patient."""

    facts: PatientFacts
    ranked: tuple[RankedTrial, ...]
    inputs_hash: str
    patient_ref_hash: str | None

    @property
    def status_counts(self) -> dict[str, int]:
        """Number of trials per status, in status order."""
        counts = Counter(item.result.status for item in self.ranked)
        return {status: counts.get(status, 0) for status in TRIAL_STATUSES}

    def structured(self) -> dict[str, Any]:
        """The JSON result (``SCREEN_OUTPUT_SCHEMA``)."""
        facts = self.facts
        years = facts.age_years()
        return {
            "as_of": facts.as_of.isoformat(),
            "inputs_hash": self.inputs_hash,
            "patient_id_hash": facts.patient_id_hash,
            "patient_ref_hash": self.patient_ref_hash,
            "patient_summary": {
                "age_years": {"min": years[0], "max": years[1]} if years else None,
                "sex": facts.sex,
                "conditions": facts.condition_resources,
                "current_medications": len(facts.medications),
                "observations": facts.observation_resources,
            },
            "trial_count": len(self.ranked),
            "status_counts": self.status_counts,
            "trials": [item.as_dict() for item in self.ranked],
            "data_notes": list(facts.notes),
            "network_used": False,
            "coverage_note": COVERAGE_NOTE,
            "disclaimer": MANDATORY_DISCLAIMER,
        }

    def summary(self) -> str:
        """Human-readable text block for MCP clients; ends with the disclaimer."""
        counts = ", ".join(f"{count} {status}" for status, count in self.status_counts.items())
        lines = [
            f"medagent screen_trial_eligibility: {len(self.ranked)} trial(s) pre-screened as of "
            f"{self.facts.as_of.isoformat()} for patient {self.facts.patient_id_hash[:12]}… "
            f"(hashed): {counts}."
        ]
        for item in self.ranked:
            result = item.result
            line = (
                f"#{item.rank} {result.trial.trial_id} {result.status}: "
                f"{result.favourable}/{len(result.results)} criteria favourable"
            )
            if result.blocking:
                line += "; blocking " + ", ".join(
                    f"{entry.criterion.id} ({entry.criterion.section} {entry.status})"
                    for entry in result.blocking
                )
            if result.open:
                line += "; open " + ", ".join(
                    f"{entry.criterion.id} ({entry.status})" for entry in result.open
                )
            lines.append(line + ".")
        lines.extend([COVERAGE_NOTE, MANDATORY_DISCLAIMER])
        return "\n".join(lines)

    def audit_events(self, screening_id: str) -> list[dict[str, Any]]:
        """De-identified audit rows: one ``screening`` row and one ``trial`` row per trial.

        Args:
            screening_id: Server-generated id that links the rows.

        Returns:
            Rows holding hashes, server-defined statuses, trial and criterion ids,
            and counts; never clinical text, codes or values.
        """
        rows: list[dict[str, Any]] = [
            {
                "event": "screening",
                "screening_id": screening_id,
                "inputs_hash": self.inputs_hash,
                "patient_id_hash": self.facts.patient_id_hash,
                "patient_ref_hash": self.patient_ref_hash,
                "as_of": self.facts.as_of.isoformat(),
                "trial_count": len(self.ranked),
            }
        ]
        for item in self.ranked:
            result = item.result
            counts = Counter(entry.status for entry in result.results)
            rows.append(
                {
                    "event": "trial",
                    "screening_id": screening_id,
                    "patient_id_hash": self.facts.patient_id_hash,
                    "trial_id": result.trial.trial_id,
                    "trial_version": result.trial.version,
                    "status": result.status,
                    "trial_rank": item.rank,
                    "met_count": counts["met"],
                    "not_met_count": counts["not_met"],
                    "insufficient_count": counts["insufficient_data"],
                    "review_count": counts["requires_human_review"],
                    "blocking_criteria": ",".join(e.criterion.id for e in result.blocking) or None,
                }
            )
        return rows


def screen_trials_request(
    arguments: Mapping[str, Any], *, path: str = "arguments"
) -> TrialScreening:
    """Screen a request shaped like ``SCREEN_INPUT_SCHEMA`` (MCP arguments or HTTP body).

    Args:
        arguments: ``bundle``, ``trials`` and optional ``patient_context``,
            ``as_of`` and ``patient_ref``.
        path: Prefix for validation messages (``arguments`` or ``body``).

    Returns:
        The ranked screening result.

    Raises:
        TrialInputError: When the arguments, a trial definition or the FHIR data
            are invalid; the message never contains caller-supplied values.
    """
    problems = validate(dict(arguments), SCREEN_INPUT_SCHEMA, path)
    if problems:
        shown = problems[:MAX_REPORTED_PROBLEMS]
        more = len(problems) - len(shown)
        suffix = f"; and {more} more" if more else ""
        raise TrialInputError(
            "invalid_arguments", "Invalid arguments: " + "; ".join(shown) + suffix
        )
    if _has_lone_surrogate(arguments):
        raise TrialInputError(
            "invalid_arguments",
            "Invalid arguments: strings must be valid Unicode (no unpaired surrogates).",
        )
    as_of = parse_as_of(arguments.get("as_of")) or datetime.now(timezone.utc).date()
    trials = parse_trials(arguments["trials"])
    facts = extract_patient_facts(
        arguments["bundle"], as_of=as_of, patient_context=arguments.get("patient_context")
    )
    ranked = rank_trials([evaluate_trial(trial, facts) for trial in trials])
    patient_ref = arguments.get("patient_ref")
    screening = TrialScreening(
        facts=facts,
        ranked=ranked,
        inputs_hash=hash_pii(canonical_json(dict(arguments))),
        patient_ref_hash=hash_pii(patient_ref) if isinstance(patient_ref, str) else None,
    )
    logger.info(
        "trial_screening_completed",
        trials=len(ranked),
        **screening.status_counts,
    )
    return screening


def screen_trials(
    bundle: Mapping[str, Any],
    trials: Sequence[Mapping[str, Any]],
    *,
    as_of: date | str | None = None,
    patient_context: Mapping[str, bool] | None = None,
    patient_ref: str | None = None,
) -> TrialScreening:
    """Pre-screen one patient's FHIR R4 Bundle against structured trial definitions.

    Args:
        bundle: FHIR R4 Bundle with one patient's resources.
        trials: Trial definitions in the medagent trial-criteria format 1.0.
        as_of: Evaluation date for age limits and recency windows (default: today, UTC).
        patient_context: Optional caller-asserted ``pregnant`` / ``breastfeeding`` flags.
        patient_ref: Optional caller reference, hashed for audit linkage only.

    Returns:
        The ranked, de-identified screening result. It is a research pre-screen:
        it never determines eligibility.

    Raises:
        TrialInputError: When an argument, a trial definition or the FHIR data is invalid.
    """
    arguments: dict[str, Any] = {"bundle": dict(bundle), "trials": [dict(t) for t in trials]}
    if isinstance(as_of, datetime):
        as_of = as_of.date()
    if as_of is not None:
        arguments["as_of"] = as_of.isoformat() if isinstance(as_of, date) else as_of
    if patient_context is not None:
        arguments["patient_context"] = dict(patient_context)
    if patient_ref is not None:
        arguments["patient_ref"] = patient_ref
    return screen_trials_request(arguments)
