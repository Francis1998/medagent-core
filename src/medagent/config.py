"""Global configuration loaded from environment variables via pydantic-settings."""

import re

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# A browser origin: scheme://host[:port], without a path, query or wildcard.
_ORIGIN = re.compile(r"https?://[a-z0-9]([a-z0-9.-]*[a-z0-9])?(:\d{1,5})?")

# OpenAI healthcare model configurations (released 2026-11-24): each pairs a base model with
# a harness tailored to clinical questions, is served by the Responses API only and is billed
# at its base model's per-token rates. The base model sets the request-shaping rules.
OPENAI_HEALTHCARE_CONFIGURATIONS: tuple[tuple[str, str], ...] = (
    ("gpt-6.2-astra-healthcare", "gpt-6.2-astra"),
    ("gpt-6.2-sol-healthcare", "gpt-6.2-sol"),
    ("gpt-6-astra-healthcare", "gpt-6-astra"),
    ("gpt-6.1-sol-healthcare", "gpt-6.1-sol"),
)


def openai_healthcare_base_model(model: str) -> str | None:
    """Return the base model of an OpenAI healthcare model configuration.

    Args:
        model: OpenAI model identifier, e.g. the value of ``OPENAI_MODEL``.

    Returns:
        The base model whose request-shaping rules ``model`` follows, or ``None`` when
        ``model`` is not a healthcare configuration.

    Raises:
        ValueError: For any other ``*-healthcare`` identifier. Only the listed configurations
            are known, and none of them is served by Chat Completions, so an unknown one fails
            at startup instead of on the first clinical request.
    """
    for configuration, base_model in OPENAI_HEALTHCARE_CONFIGURATIONS:
        if model == configuration:
            return base_model
    if model.strip().lower().rsplit("/", 1)[-1].endswith("-healthcare"):
        supported = ", ".join(name for name, _ in OPENAI_HEALTHCARE_CONFIGURATIONS)
        raise ValueError(
            f"OPENAI_MODEL={model!r} is not a supported OpenAI healthcare model configuration "
            f"(Responses API only); use one of: {supported}"
        )
    return None


class Settings(BaseSettings):
    """Application-wide settings resolved from environment / .env file.

    All fields are typed and validated at startup. Missing required keys
    that have no default will raise a validation error immediately, preventing
    silent misconfiguration at runtime.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM ---
    openai_api_key: str = Field(default="", description="OpenAI API key")
    anthropic_api_key: str = Field(default="", description="Anthropic API key")
    google_api_key: str = Field(default="", description="Google Generative AI key")
    kimi_api_key: str = Field(default="", description="Kimi/Moonshot API key")

    openai_model: str = Field(default="gpt-6.2-sol")
    anthropic_model: str = Field(default="claude-opus-5-5")
    google_model: str = Field(default="gemini-4-argon")
    kimi_model: str = Field(default="kimi-k3.1-pro")
    kimi_base_url: str = Field(
        default="https://api.moonshot.ai/v1",
        description="Kimi/Moonshot OpenAI-compatible endpoint (api.moonshot.cn for China)",
    )
    llm_max_output_tokens: int = Field(
        default=32_768,
        ge=256,
        le=1_048_576,
        description="Completion budget per LLM call, including reasoning/thinking tokens",
    )

    @field_validator("openai_model")
    @classmethod
    def _check_openai_healthcare_configuration(cls, value: str) -> str:
        """Reject an unknown ``*-healthcare`` OpenAI model at startup."""
        openai_healthcare_base_model(value)
        return value

    # --- External APIs ---
    pubmed_api_key: str = Field(default="")
    pubmed_email: str = Field(default="medagent@example.com")
    openfda_api_key: str = Field(default="")

    # --- Database ---
    database_url: str = Field(default="sqlite+aiosqlite:///./data/audit.db")

    # --- Agent Timeouts (seconds) ---
    agent_confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    agent_total_timeout_seconds: int = Field(default=120, ge=10)
    agent_entity_extraction_timeout: int = Field(default=10, ge=1)
    agent_retrieval_timeout: int = Field(default=20, ge=1)
    agent_reasoning_timeout: int = Field(default=90, ge=10)

    # --- Knowledge Base ---
    kb_embedding_path: str = Field(default="./data/biowordvec_pubmed_mesh_200d.bin")
    kb_index_path: str = Field(default="./data/kb_index/")

    # --- API Server ---
    api_host: str = Field(default="127.0.0.1")
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_workers: int = Field(default=1, ge=1)
    log_level: str = Field(default="INFO")

    # --- Security ---
    pii_hash_salt: str = Field(
        default="insecure-default-change-me",
        description="Hex salt for PII field hashing — must be overridden in production",
    )

    # --- CDS Hooks ---
    cds_hooks_cors_origins: str = Field(
        default="",
        validation_alias="MEDAGENT_CDS_HOOKS_CORS_ORIGINS",
        description=(
            "Comma-separated browser origins allowed to call /cds-services (CORS opt-in); "
            "empty means no CORS headers on /cds-services"
        ),
    )

    @field_validator("cds_hooks_cors_origins")
    @classmethod
    def _normalise_cds_hooks_cors_origins(cls, value: str) -> str:
        """Validate the CDS Hooks CORS allow-list and store it as ``a,b`` (lower case)."""
        origins: list[str] = []
        for item in re.split(r"[,\s]+", value.strip()):
            origin = item.rstrip("/").lower()
            if not origin:
                continue
            if not _ORIGIN.fullmatch(origin):
                raise ValueError(
                    "MEDAGENT_CDS_HOOKS_CORS_ORIGINS must list browser origins such as "
                    "https://sandbox.cds-hooks.org (scheme://host[:port]; no wildcard or path)"
                )
            if origin not in origins:
                origins.append(origin)
        return ",".join(origins)

    @property
    def cds_hooks_cors_origin_list(self) -> tuple[str, ...]:
        """Origins allowed to call ``/cds-services`` from a browser; empty disables CORS."""
        return tuple(origin for origin in self.cds_hooks_cors_origins.split(",") if origin)

    # --- Evaluation ---
    medqa_data_path: str = Field(default="./data/medqa_usmle_4_options_test.jsonl")
    drugbank_test_path: str = Field(default="./data/drugbank_interactions_test.json")
    eval_max_samples: int = Field(default=100, ge=1)


# Singleton imported throughout the package
settings = Settings()
