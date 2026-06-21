"""Drug interaction retrieval via OpenFDA and DrugBank-compatible REST APIs.

Safety invariant: every DrugInteractionWarning surfaced to the caller must
be validated against AT LEAST 2 independent data sources. Warnings that
cannot be cross-validated are logged and suppressed — never surfaced as
validated=True.
"""

from __future__ import annotations

import asyncio
from itertools import combinations
from typing import Any

import aiohttp
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from medagent.config import settings
from medagent.logging_config import get_logger
from medagent.models import DrugInteractionWarning, Medication, Severity

logger = get_logger(__name__)

_OPENFDA_BASE = "https://api.fda.gov/drug/label.json"
_RXNORM_INTERACTION_BASE = "https://rxnav.nlm.nih.gov/REST/interaction"


class DrugInteractionClient:
    """Checks drug-drug interactions via OpenFDA and RxNorm Interaction API.

    Two independent sources are queried and their results cross-validated.
    Only interactions confirmed by both sources are returned as validated=True.

    Args:
        openfda_api_key: OpenFDA API key (optional, extends rate limits).
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        openfda_api_key: str = "",
        timeout: int = 20,
    ) -> None:
        self._openfda_key = openfda_api_key or settings.openfda_api_key
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def check_interactions(
        self, medications: list[Medication]
    ) -> list[DrugInteractionWarning]:
        """Check all pairwise drug interactions for a medication list.

        Args:
            medications: List of patient medications.

        Returns:
            List of DrugInteractionWarning objects, each validated by ≥2 sources.
        """
        if len(medications) < 2:
            return []

        pairs = list(combinations(medications, 2))
        tasks = [self._check_pair(a, b) for a, b in pairs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        warnings: list[DrugInteractionWarning] = []
        for result in results:
            if isinstance(result, list):
                warnings.extend(result)
            elif isinstance(result, Exception):
                logger.warning("interaction_check_error", error=str(result))

        logger.info("drug_interactions_found", count=len(warnings))
        return warnings

    async def _check_pair(
        self, drug_a: Medication, drug_b: Medication
    ) -> list[DrugInteractionWarning]:
        """Query both sources for a single drug pair and cross-validate."""
        sources_found: list[str] = []
        interaction_data: list[dict[str, Any]] = []

        # Source 1: RxNorm Interaction API (open, no key required)
        rxnorm_result = await self._query_rxnorm(drug_a.name, drug_b.name)
        if rxnorm_result:
            sources_found.append("rxnorm")
            interaction_data.extend(rxnorm_result)

        # Source 2: OpenFDA label search
        openfda_result = await self._query_openfda(drug_a.name, drug_b.name)
        if openfda_result:
            sources_found.append("openfda")
            interaction_data.extend(openfda_result)

        if len(sources_found) < 2:
            # Cannot validate with <2 sources — suppress per safety invariant
            if sources_found and interaction_data:
                logger.info(
                    "interaction_suppressed_insufficient_sources",
                    drug_a=drug_a.name,
                    drug_b=drug_b.name,
                    sources=sources_found,
                )
            return []

        # Cross-validated — build the warning
        combined_mechanism = " | ".join(
            d.get("mechanism", "Unknown mechanism") for d in interaction_data[:2]
        )
        combined_consequence = " | ".join(
            d.get("consequence", "Review required") for d in interaction_data[:2]
        )
        severity_str = interaction_data[0].get("severity", "MODERATE")
        try:
            severity = Severity(severity_str.upper())
        except ValueError:
            severity = Severity.MODERATE

        try:
            warning = DrugInteractionWarning(
                drug_a=drug_a.name,
                drug_b=drug_b.name,
                severity=severity,
                mechanism=combined_mechanism,
                clinical_consequence=combined_consequence,
                sources=sources_found,
                validated=True,
            )
        except Exception as exc:
            logger.warning("interaction_build_error", error=str(exc))
            return []

        return [warning]

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=False,
    )
    async def _query_rxnorm(self, drug_a: str, drug_b: str) -> list[dict[str, Any]] | None:
        """Query the NLM RxNorm Interaction API for a drug pair."""
        url = f"{_RXNORM_INTERACTION_BASE}/list.json"
        params = {"drugList": f"{drug_a};{drug_b}"}

        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        return None
                    data: dict[str, Any] = await resp.json(content_type=None)

            full_result = data.get("fullInteractionTypeGroup", [])
            if not full_result:
                return None

            interactions: list[dict[str, Any]] = []
            for group in full_result:
                for interaction_type in group.get("fullInteractionType", []):
                    for pair in interaction_type.get("interactionPair", []):
                        interactions.append(
                            {
                                "mechanism": pair.get("description", "Unknown"),
                                "consequence": pair.get("severity", "Review required"),
                                "severity": _map_rxnorm_severity(pair.get("severity", "moderate")),
                            }
                        )
            return interactions or None
        except Exception as exc:
            logger.debug("rxnorm_query_failed", error=str(exc))
            return None

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=False,
    )
    async def _query_openfda(self, drug_a: str, drug_b: str) -> list[dict[str, Any]] | None:
        """Query OpenFDA drug label API for warnings mentioning drug_b in drug_a's label."""
        search_query = f'openfda.brand_name:"{drug_a}" AND warnings:"{drug_b}"'
        params: dict[str, str] = {
            "search": search_query,
            "limit": "1",
        }
        if self._openfda_key:
            params["api_key"] = self._openfda_key

        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.get(_OPENFDA_BASE, params=params) as resp:
                    if resp.status == 404:
                        return None
                    if resp.status != 200:
                        return None
                    data: dict[str, Any] = await resp.json(content_type=None)

            results = data.get("results", [])
            if not results:
                return None

            warnings_text = results[0].get("warnings", [""])[0]
            if drug_b.lower() not in warnings_text.lower():
                return None

            return [
                {
                    "mechanism": "See FDA label warnings section",
                    "consequence": f"Potential interaction noted in {drug_a} label",
                    "severity": "MODERATE",
                }
            ]
        except Exception as exc:
            logger.debug("openfda_query_failed", error=str(exc))
            return None


def _map_rxnorm_severity(rxnorm_severity: str) -> str:
    """Map RxNorm severity strings to our Severity enum values."""
    mapping = {
        "N/A": "UNKNOWN",
        "minor": "LOW",
        "moderate": "MODERATE",
        "major": "HIGH",
        "contraindicated": "CRITICAL",
    }
    return mapping.get(rxnorm_severity.lower(), "MODERATE")
