"""Settings, loaded from the environment.

Two properties matter here. The defaults are the zero-cost path, so a clean
clone with no ``.env`` runs entirely on the mock provider with no network. And
every credential is a :class:`~pydantic.SecretStr`, so it cannot reach a repr, a
log line or a traceback.

See ``docs/operations.md`` section 3.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Final, Literal

from pydantic import Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["KEYLESS_PROVIDERS", "KNOWN_PROVIDERS", "Settings", "get_settings"]

Environment = Literal["dev", "test", "prod"]
RuntimeKind = Literal["native", "graph"]

#: Every provider the registry knows how to build. A name outside this set is a
#: typo, not a provider that happens to be unconfigured, so it fails loudly.
KNOWN_PROVIDERS: Final[frozenset[str]] = frozenset(
    {"mock", "ollama", "openai", "anthropic", "google", "groq", "openrouter"}
)

#: Providers that need no credential. They are always available, which is what
#: lets a chain fall through to something that always works.
KEYLESS_PROVIDERS: Final[frozenset[str]] = frozenset({"mock", "ollama"})


class Settings(BaseSettings):
    """Runtime configuration. Every field has a working default."""

    model_config = SettingsConfigDict(
        env_prefix="FOREMAN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Environment = "dev"

    # --- Providers -----------------------------------------------------------
    # A tier resolves to an ordered chain. A provider with no key is skipped,
    # which is why these default to the mock and work with no .env at all.
    tier_small: list[str] = Field(default=["mock"])
    tier_large: list[str] = Field(default=["mock"])

    ollama_base_url: str = "http://localhost:11434"
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None

    # --- Runtime -------------------------------------------------------------
    runtime: RuntimeKind = "native"
    max_steps: int = Field(default=12, gt=0)
    max_tokens_per_run: int = Field(default=40_000, gt=0)

    # --- Budget --------------------------------------------------------------
    # Checked before a call, never after. A budget found after the spend is a
    # report, not a control.
    max_cost_per_run_cents: int = Field(default=10, ge=0)
    max_cost_per_day_cents: int = Field(default=100, ge=0)
    kill_switch: bool = False

    # --- Optional services ---------------------------------------------------
    # Each is off by default and has a tested in-process fallback.
    enable_graph_store: bool = False
    enable_pgvector: bool = False
    enable_langfuse: bool = False

    # --- Storage -------------------------------------------------------------
    run_store_url: str = "sqlite:///./foreman.db"
    trace_dir: str = "./traces"

    @field_validator("tier_small", "tier_large")
    @classmethod
    def _reject_unknown_providers(cls, chain: list[str], info: ValidationInfo) -> list[str]:
        """Fail at startup on a provider name that does not exist.

        A missing credential and a misspelled name look identical once you are
        only asking "is this configured?" — both answer no. The first is normal
        and should be skipped; the second is a mistake that would otherwise
        silently shorten the chain. Catching it here means the process refuses
        to start rather than quietly running on a fallback nobody chose.
        """
        unknown = [name for name in chain if name not in KNOWN_PROVIDERS]
        if unknown:
            raise ValueError(
                f"{info.field_name}: unknown provider(s) {sorted(unknown)}. "
                f"Known providers are {sorted(KNOWN_PROVIDERS)}."
            )
        if not chain:
            raise ValueError(f"{info.field_name}: a provider chain cannot be empty.")
        return chain

    def provider_configured(self, name: str) -> bool:
        """Whether a provider has what it needs to run.

        The registry uses this to *skip* a provider rather than fail on it,
        which is what lets a chain fall through to the mock. That behaviour is
        only safe for names that exist, so an unknown one raises instead of
        quietly reporting "not configured".
        """
        if name not in KNOWN_PROVIDERS:
            raise ValueError(
                f"Unknown provider {name!r}. Known providers are {sorted(KNOWN_PROVIDERS)}."
            )
        if name in KEYLESS_PROVIDERS:
            return True
        key: SecretStr | None = getattr(self, f"{name}_api_key", None)
        return key is not None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """The single load point for configuration. Cached for the process."""
    return Settings()
