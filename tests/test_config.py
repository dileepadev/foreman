"""Settings behaviour.

The two properties worth protecting here are the zero-cost default (a clean
clone runs with no credentials and no network) and the guarantee that a
credential cannot escape into a log, a repr or a traceback.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from foreman.core.config import (
    KEYLESS_PROVIDERS,
    KNOWN_PROVIDERS,
    Settings,
    get_settings,
)

SECRET = "sk-not-a-real-key-2f8a1c"


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep the developer's real .env and exported FOREMAN_* vars out of these tests.

    Settings reads a relative ``.env``, so running from an empty directory is
    enough to guarantee the defaults under test are the real defaults.
    """
    for key in [k for k in os.environ if k.startswith("FOREMAN_")]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)


def _settings(**overrides: object) -> Settings:
    return Settings(**overrides)  # type: ignore[arg-type]


class TestZeroCostDefault:
    def test_both_tiers_default_to_mock(self) -> None:
        s = _settings()
        assert s.tier_small == ["mock"]
        assert s.tier_large == ["mock"]

    def test_no_credential_is_set_by_default(self) -> None:
        s = _settings()
        hosted = KNOWN_PROVIDERS - KEYLESS_PROVIDERS
        assert not [name for name in hosted if s.provider_configured(name)]

    def test_optional_services_are_all_off(self) -> None:
        s = _settings()
        assert s.enable_graph_store is False
        assert s.enable_pgvector is False
        assert s.enable_langfuse is False


class TestSecretsDoNotLeak:
    """A credential must not reach a repr, a log line or a traceback."""

    @pytest.fixture
    def configured(self) -> Settings:
        # Passed as a plain string on purpose. Pydantic coerces it into the
        # SecretStr field, and if someone ever downgrades that field to a bare
        # str these tests still build and fail with "the secret leaked" rather
        # than erroring on the fixture.
        return _settings(openai_api_key=SECRET)

    def test_absent_from_repr(self, configured: Settings) -> None:
        assert SECRET not in repr(configured)

    def test_absent_from_str_of_the_field(self, configured: Settings) -> None:
        assert SECRET not in str(configured.openai_api_key)

    def test_absent_from_model_dump(self, configured: Settings) -> None:
        assert SECRET not in str(configured.model_dump())

    def test_absent_from_model_dump_json(self, configured: Settings) -> None:
        assert SECRET not in configured.model_dump_json()

    def test_absent_from_an_exception_message(self, configured: Settings) -> None:
        """Settings often land in error messages; the credential must not."""
        assert SECRET not in str(ValueError(f"boom {configured}"))

    def test_still_retrievable_on_purpose(self, configured: Settings) -> None:
        """Masking must not mean unusable — the value is there when asked for."""
        assert isinstance(configured.openai_api_key, SecretStr)
        assert configured.openai_api_key.get_secret_value() == SECRET


class TestProviderConfigured:
    @pytest.mark.parametrize("name", sorted(KEYLESS_PROVIDERS))
    def test_keyless_providers_are_always_available(self, name: str) -> None:
        assert _settings().provider_configured(name) is True

    def test_hosted_provider_without_a_key_is_not_configured(self) -> None:
        assert _settings().provider_configured("openai") is False

    def test_hosted_provider_with_a_key_is_configured(self) -> None:
        s = _settings(groq_api_key=SecretStr(SECRET))
        assert s.provider_configured("groq") is True

    def test_a_key_configures_only_its_own_provider(self) -> None:
        s = _settings(groq_api_key=SecretStr(SECRET))
        assert s.provider_configured("openai") is False

    def test_unknown_name_raises_rather_than_reporting_unconfigured(self) -> None:
        """The distinction this protects: absent credential vs. misspelled name.

        Both used to answer "not configured", so a typo silently shortened the
        chain instead of failing.
        """
        with pytest.raises(ValueError, match="Unknown provider"):
            _settings().provider_configured("openai_typo")


class TestProviderChainValidation:
    @pytest.mark.parametrize("field", ["tier_small", "tier_large"])
    def test_unknown_provider_is_rejected_at_startup(self, field: str) -> None:
        with pytest.raises(ValidationError, match="unknown provider"):
            _settings(**{field: ["openai_typo"]})

    @pytest.mark.parametrize("field", ["tier_small", "tier_large"])
    def test_empty_chain_is_rejected(self, field: str) -> None:
        with pytest.raises(ValidationError, match="cannot be empty"):
            _settings(**{field: []})

    def test_a_valid_chain_is_accepted_in_order(self) -> None:
        s = _settings(tier_large=["anthropic", "openrouter", "ollama"])
        assert s.tier_large == ["anthropic", "openrouter", "ollama"]

    def test_one_bad_name_rejects_the_whole_chain(self) -> None:
        with pytest.raises(ValidationError, match="unknown provider"):
            _settings(tier_small=["ollama", "nope", "mock"])


class TestBounds:
    @pytest.mark.parametrize("field", ["max_steps", "max_tokens_per_run"])
    def test_must_be_positive(self, field: str) -> None:
        with pytest.raises(ValidationError):
            _settings(**{field: 0})

    @pytest.mark.parametrize("field", ["max_cost_per_run_cents", "max_cost_per_day_cents"])
    def test_budget_may_be_zero_but_not_negative(self, field: str) -> None:
        assert _settings(**{field: 0})
        with pytest.raises(ValidationError):
            _settings(**{field: -1})


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()
    assert get_settings() is get_settings()
    get_settings.cache_clear()
