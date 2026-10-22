"""Unit tests for lakegen.core.config.EnvConfig."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from lakegen.core.config import EnvConfig


def test_default_is_frozen_builtin_fallback() -> None:
    config = EnvConfig.default()
    assert config.base_url is None
    assert config.model == "gpt-4o-mini"
    assert config.provider == "openai"


def test_default_ignores_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    assert EnvConfig.default() == EnvConfig()


def test_from_env_falls_back_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    config = EnvConfig.from_env()
    assert config.model == "gpt-4o-mini"
    assert config.base_url is None


def test_from_env_reads_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    assert EnvConfig.from_env().model == "gpt-4o"


def test_from_env_reads_base_url_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    assert EnvConfig.from_env().base_url == "https://openrouter.ai/api/v1"


def test_from_env_provider_keeps_builtin_room(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    assert EnvConfig.from_env().provider == "openai"


def test_env_config_is_immutable() -> None:
    config = EnvConfig.from_env()
    with pytest.raises(FrozenInstanceError):
        config.model = "mutated"
