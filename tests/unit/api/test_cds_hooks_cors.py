"""CORS on ``/cds-services`` is opt-in and scoped; the app-wide policy is unchanged."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from medagent.api import main
from medagent.config import Settings, settings

SANDBOX = "https://sandbox.cds-hooks.org"
PREFLIGHT = {
    "Origin": SANDBOX,
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "authorization,content-type",
}


async def call(method: str, url: str, **kwargs: Any) -> httpx.Response:
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://medagent.test") as client:
        return await client.request(method, url, **kwargs)


def cors_headers(response: httpx.Response) -> dict[str, str]:
    return {k: v for k, v in response.headers.items() if k.startswith("access-control-")}


async def test_cds_services_send_no_cors_headers_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "cds_hooks_cors_origins", "")

    discovery = await call("GET", "/cds-services", headers={"Origin": SANDBOX})
    preflight = await call("OPTIONS", "/cds-services/medagent-medication-safety", headers=PREFLIGHT)
    health = await call("GET", "/health", headers={"Origin": SANDBOX})

    assert discovery.status_code == 200
    assert cors_headers(discovery) == {}
    assert cors_headers(preflight) == {}
    assert preflight.status_code == 405
    # Other paths keep the pre-existing app-wide policy.
    assert health.headers["access-control-allow-origin"] == "*"


async def test_allow_listed_origins_get_cors_on_cds_services_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "cds_hooks_cors_origins", f"{SANDBOX},http://localhost:3000")

    discovery = await call("GET", "/cds-services", headers={"Origin": SANDBOX})
    preflight = await call(
        "OPTIONS", "/cds-services/medagent-medication-safety/feedback", headers=PREFLIGHT
    )
    other_origin = await call("GET", "/cds-services", headers={"Origin": "https://evil.example"})
    other_preflight = await call(
        "OPTIONS",
        "/cds-services/medagent-medication-safety",
        headers={**PREFLIGHT, "Origin": "https://evil.example"},
    )
    health = await call("GET", "/health", headers={"Origin": SANDBOX})

    assert discovery.headers["access-control-allow-origin"] == SANDBOX
    assert "access-control-allow-credentials" not in discovery.headers
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == SANDBOX
    assert set(preflight.headers["access-control-allow-methods"].split(", ")) == {
        "GET",
        "POST",
    }
    allowed_headers = preflight.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed_headers and "content-type" in allowed_headers
    assert "access-control-allow-origin" not in other_origin.headers
    assert other_preflight.status_code == 400
    assert "access-control-allow-origin" not in other_preflight.headers
    # The allow-list does not leak to other paths, which keep their own policy.
    assert health.headers["access-control-allow-origin"] == "*"


def test_cors_origin_setting_is_normalised() -> None:
    configured = Settings(
        _env_file=None,
        MEDAGENT_CDS_HOOKS_CORS_ORIGINS=(
            " https://Sandbox.CDS-Hooks.org/ , http://localhost:3000 https://sandbox.cds-hooks.org"
        ),
    )

    assert (
        configured.cds_hooks_cors_origins == "https://sandbox.cds-hooks.org,http://localhost:3000"
    )
    assert configured.cds_hooks_cors_origin_list == (
        "https://sandbox.cds-hooks.org",
        "http://localhost:3000",
    )
    assert Settings(_env_file=None).cds_hooks_cors_origin_list == ()


def test_cors_origin_setting_reads_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDAGENT_CDS_HOOKS_CORS_ORIGINS", SANDBOX)

    assert Settings(_env_file=None).cds_hooks_cors_origin_list == (SANDBOX,)


@pytest.mark.parametrize(
    "value",
    ["*", "https://*.example.org", "https://sandbox.cds-hooks.org/path", "sandbox.cds-hooks.org"],
)
def test_wildcards_and_non_origins_are_rejected_at_startup(value: str) -> None:
    with pytest.raises(ValidationError, match="MEDAGENT_CDS_HOOKS_CORS_ORIGINS"):
        Settings(_env_file=None, MEDAGENT_CDS_HOOKS_CORS_ORIGINS=value)
