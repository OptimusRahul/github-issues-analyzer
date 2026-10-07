"""Load triage settings from .github/issue-triage.yml."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """The config file has an unknown key or an invalid value."""


@dataclass
class DuplicatesConfig:
    enabled: bool = True
    threshold: float = 0.86
    max_candidates: int = 3
    label: str | None = "possible-duplicate"
    closed_window_days: int = 180


@dataclass
class EmbeddingsConfig:
    provider: str = "local"  # local | openai
    model: str = "BAAI/bge-small-en-v1.5"
    base_url: str | None = None
    api_key_env: str | None = None


@dataclass
class LLMConfig:
    base_url: str | None = None
    model: str | None = None
    api_key_env: str = "TRIAGE_LLM_KEY"

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.model)


@dataclass
class ModelsConfig:
    embeddings: EmbeddingsConfig = field(default_factory=EmbeddingsConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)


@dataclass
class LimitsConfig:
    max_llm_calls_per_run: int = 50


@dataclass
class Config:
    dry_run: bool = True
    duplicates: DuplicatesConfig = field(default_factory=DuplicatesConfig)
    digest: dict[str, Any] = field(default_factory=dict)  # read by the digest in v0.2
    exclude_labels: list[str] = field(default_factory=list)
    comments_window_days: int = 180
    models: ModelsConfig = field(default_factory=ModelsConfig)
    limits: LimitsConfig = field(default_factory=LimitsConfig)


_NESTED = {
    (Config, "duplicates"): DuplicatesConfig,
    (Config, "models"): ModelsConfig,
    (Config, "limits"): LimitsConfig,
    (ModelsConfig, "embeddings"): EmbeddingsConfig,
    (ModelsConfig, "llm"): LLMConfig,
}


def _build(cls: type, data: Any, path: str):
    if data is None:
        return cls()
    if not isinstance(data, dict):
        raise ConfigError(f"{path or 'config file'}: expected a mapping")
    known = {f.name for f in fields(cls)}
    kwargs = {}
    for key, value in data.items():
        name = f"{path}.{key}" if path else key
        if key not in known:
            raise ConfigError(f"{name}: unknown setting")
        nested = _NESTED.get((cls, key))
        kwargs[key] = _build(nested, value, name) if nested else value
    return cls(**kwargs)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate(cfg: Config) -> None:
    dup = cfg.duplicates
    checks = [
        (isinstance(cfg.dry_run, bool), "dry_run: must be true or false"),
        (
            isinstance(dup.threshold, (int, float)) and not isinstance(dup.threshold, bool) and 0 < dup.threshold <= 1,
            "duplicates.threshold: must be a number greater than 0 and at most 1",
        ),
        (_is_int(dup.max_candidates) and 1 <= dup.max_candidates <= 10, "duplicates.max_candidates: must be an integer from 1 to 10"),
        (_is_int(dup.closed_window_days) and dup.closed_window_days >= 0, "duplicates.closed_window_days: must be a non-negative integer"),
        (dup.label is None or isinstance(dup.label, str), "duplicates.label: must be text or null"),
        (isinstance(cfg.exclude_labels, list), "exclude_labels: must be a list"),
        (_is_int(cfg.comments_window_days) and cfg.comments_window_days >= 0, "comments_window_days: must be a non-negative integer"),
        (cfg.models.embeddings.provider in ("local", "openai"), "models.embeddings.provider: must be 'local' or 'openai'"),
        (
            _is_int(cfg.limits.max_llm_calls_per_run) and cfg.limits.max_llm_calls_per_run >= 0,
            "limits.max_llm_calls_per_run: must be a non-negative integer",
        ),
    ]
    for ok, message in checks:
        if not ok:
            raise ConfigError(message)


def load_config(path: Path | None = None) -> Config:
    data = None
    if path is not None and path.exists():
        try:
            data = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"{path}: invalid YAML: {e}") from e
    cfg = _build(Config, data, "")
    env_dry_run = os.environ.get("TRIAGE_DRY_RUN")
    if env_dry_run is not None:
        cfg.dry_run = env_dry_run.strip().lower() not in ("0", "false", "no")
    _validate(cfg)
    return cfg
