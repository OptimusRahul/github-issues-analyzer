import pytest

from triage.config import ConfigError, load_config


def write(tmp_path, text):
    path = tmp_path / "issue-triage.yml"
    path.write_text(text)
    return path


def test_defaults_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("TRIAGE_DRY_RUN", raising=False)
    cfg = load_config(tmp_path / "missing.yml")
    assert cfg.dry_run is True
    assert cfg.duplicates.threshold == 0.86
    assert cfg.duplicates.label == "possible-duplicate"
    assert cfg.models.embeddings.provider == "local"
    assert cfg.models.llm.enabled is False


def test_loads_nested_values(tmp_path, monkeypatch):
    monkeypatch.delenv("TRIAGE_DRY_RUN", raising=False)
    cfg = load_config(write(tmp_path, """
dry_run: false
duplicates:
  threshold: 0.9
  label: null
exclude_labels: [wontfix]
digest:
  target: issue
models:
  llm:
    base_url: http://localhost:11434/v1
    model: some-model
"""))
    assert cfg.dry_run is False
    assert cfg.duplicates.threshold == 0.9
    assert cfg.duplicates.label is None
    assert cfg.exclude_labels == ["wontfix"]
    assert cfg.digest.target == "issue" and cfg.digest.waiting_days == 14
    assert cfg.models.llm.enabled is True


def test_unknown_key_names_the_field(tmp_path):
    with pytest.raises(ConfigError, match=r"duplicates\.thresold"):
        load_config(write(tmp_path, "duplicates:\n  thresold: 0.9\n"))


def test_invalid_value_names_the_field(tmp_path):
    with pytest.raises(ConfigError, match=r"duplicates\.threshold"):
        load_config(write(tmp_path, "duplicates:\n  threshold: high\n"))


def test_invalid_provider_names_the_field(tmp_path):
    with pytest.raises(ConfigError, match=r"models\.embeddings\.provider"):
        load_config(write(tmp_path, "models:\n  embeddings:\n    provider: magic\n"))


def test_invalid_yaml_is_a_config_error(tmp_path):
    with pytest.raises(ConfigError, match="invalid YAML"):
        load_config(write(tmp_path, "duplicates: [unclosed\n"))


def test_env_overrides_dry_run(monkeypatch):
    monkeypatch.setenv("TRIAGE_DRY_RUN", "false")
    assert load_config(None).dry_run is False


def test_digest_to_discussions_is_rejected_until_supported(tmp_path):
    with pytest.raises(ConfigError, match=r"digest\.target.*discussion"):
        load_config(write(tmp_path, "digest:\n  target: discussion\n"))


def test_unknown_digest_target_names_the_field(tmp_path):
    with pytest.raises(ConfigError, match=r"digest\.target"):
        load_config(write(tmp_path, "digest:\n  target: email\n"))
