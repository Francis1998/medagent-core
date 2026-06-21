"""PubMed NCBI E-utilities retrieval client.

Queries PubMed by MeSH terms and returns structured RetrievedDocument
objects with titles, abstracts (as snippets), and PMID-based URLs.

Rate limits:
  - Without API key: 3 req/s
  - With API key:   10 req/s

All requests use tenacity retry with exponential back-off to handle
transient 429 / 503 responses from the NCBI API.
"""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlencode

import aiohttp
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from medagent.config import settings
from medagent.logging_config import get_logger
from medagent.models import RetrievedDocument

logger = get_logger(__name__)

_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
_EINFO_TIMEOUT = aiohttp.ClientTimeout(total=settings.agent_retrieval_timeout)


class PubMedClient:
    """Async PubMed search and fetch client.

    Args:
        api_key: NCBI API key (optional but raises rate limit to 10 req/s).
        email: Contact email required by NCBI ToS.
        max_results: Maximum PMIDs to retrieve per query.
        timeout: HTTP timeout in seconds.
    """

    def __init__(
        self,
        api_key: str = "",
        email: str = "",
        max_results: int = 5,
        timeout: int = 20,
    ) -> None:
        self._api_key = api_key or settings.pubmed_api_key
        self._email = email or settings.pubmed_email
        self._max_results = max_results
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def search(
        self,
        mesh_terms: list[str],
    ) -> list[RetrievedDocument]:
        """Search PubMed for documents matching MeSH terms.

        Args:
            mesh_terms: List of MeSH terms to query (combined with OR).

        Returns:
            List of RetrievedDocument objects ranked by PubMed relevance.
        """
        if not mesh_terms:
            return []

        query = " OR ".join(f'"{t}"[MeSH Terms]' for t in mesh_terms[:5])
        pmids = await self._esearch(query)
        if not pmids:
            return []

        docs = await self._efetch(pmids)
        logger.info("pubmed_results", query_terms=len(mesh_terms), returned=len(docs))
        return docs

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _esearch(self, query: str) -> list[str]:
        """Run ESearch and return a list of PMIDs."""
        params: dict[str, str] = {
            "db": "pubmed",
            "term": query,
            "retmax": str(self._max_results),
            "retmode": "json",
            "tool": "medagent-core",
            "email": self._email,
        }
        if self._api_key:
            params["api_key"] = self._api_key

        url = f"{_ESEARCH_URL}?{urlencode(params)}"
        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                data: dict[str, Any] = await resp.json()

        id_list: list[str] = data.get("esearchresult", {}).get("idlist", [])
        return id_list

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _efetch(self, pmids: list[str]) -> list[RetrievedDocument]:
        """Fetch article details for a list of PMIDs using EFetch."""
        params: dict[str, str] = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "json",
            "rettype": "abstract",
            "tool": "medagent-core",
            "email": self._email,
        }
        if self._api_key:
            params["api_key"] = self._api_key

        url = f"{_EFETCH_URL}?{urlencode(params)}"
        docs: list[RetrievedDocument] = []

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.warning("pubmed_efetch_error", status=resp.status)
                    return docs
                data: dict[str, Any] = await resp.json(content_type=None)

        result = data.get("PubmedArticleSet", {})
        articles = result.get("PubmedArticle", [])
        if isinstance(articles, dict):
            articles = [articles]

        for article in articles:
            try:
                doc = _parse_article(article)
                if doc:
                    docs.append(doc)
            except Exception as exc:
                logger.warning("pubmed_parse_error", error=str(exc))

        return docs


def _parse_article(article: dict[str, Any]) -> RetrievedDocument | None:
    """Parse a PubmedArticle dict into a RetrievedDocument."""
    medline = article.get("MedlineCitation", {})
    pmid = str(medline.get("PMID", {}).get("#text") or medline.get("PMID", ""))

    article_data = medline.get("Article", {})
    title = _extract_text(article_data.get("ArticleTitle", ""))

    abstract_text = article_data.get("Abstract", {}).get("AbstractText", "")
    snippet = _extract_text(abstract_text)[:500]

    pub_date = (
        article_data.get("Journal", {}).get("JournalIssue", {}).get("PubDate", {}).get("Year")
    )

    # Extract MeSH terms
    mesh_list = medline.get("MeshHeadingList", {}).get("MeshHeading", [])
    if isinstance(mesh_list, dict):
        mesh_list = [mesh_list]
    mesh_terms = [
        _extract_text(m.get("DescriptorName", "")) for m in mesh_list if m.get("DescriptorName")
    ][:10]

    if not pmid or not title:
        return None

    return RetrievedDocument(
        source="pubmed",
        doc_id=pmid,
        title=title,
        snippet=snippet,
        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        relevance_score=0.7,  # PubMed relevance ranking is opaque; use a fixed score
        mesh_terms=mesh_terms,
        published_date=str(pub_date) if pub_date else None,
    )


def _extract_text(value: Any) -> str:
    """Recursively extract plain text from NCBI JSON string or dict."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("#text") or value.get("b") or str(value)
    if isinstance(value, list):
        return " ".join(_extract_text(v) for v in value)
    return str(value) if value else ""
