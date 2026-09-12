"""Settings, loaded from the environment.

Two properties matter here. The defaults are the zero-cost path, so a clean
clone with no ``.env`` runs entirely on the mock provider with no network. And
every credential is a :class:`~pydantic.SecretStr`, so it cannot reach a repr, a
log line or a traceback.

See ``docs/operations.md`` section 3.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings", "get_settings"]

Environment = Literal["dev", "test", "prod"]
RuntimeKind = Literal["native", "graph"]


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

    def provider_configured(self, name: str) -> bool:
        """Whether a provider has what it needs to run.

        Used by the registry to skip a provider rather than fail on it, which is
        what lets the default chain fall through to the mock.
        """
        if name in ("mock", "ollama"):
            return True
        key = getattr(self, f"{name}_api_key", None)
        return key is not None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """The single load point for configuration. Cached for the process."""
    return Settings()
