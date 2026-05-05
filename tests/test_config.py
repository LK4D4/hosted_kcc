from pathlib import Path

import pytest

from hosted_kcc.config import ConfigError, load_config


def test_default_config_uses_standard_container_paths(tmp_path, monkeypatch):
    monkeypatch.delenv("HOSTED_KCC_INPUT_ROOTS", raising=False)
    monkeypatch.delenv("HOSTED_KCC_OUTPUT_ROOT", raising=False)

    cfg = load_config(config_path=tmp_path / "config.toml")

    assert cfg.paths.input_roots == [Path("/input")]
    assert cfg.paths.output_root == Path("/output")
    assert cfg.paths.work_root == Path("/data/work")
    assert cfg.paths.database == Path("/data/hosted-kcc.sqlite3")
    assert cfg.output.mode == "mirror"
    assert cfg.conversion.format == "CBZ"


def test_env_overrides_are_applied_and_generated(tmp_path, monkeypatch):
    config_path = tmp_path / "config.toml"
    monkeypatch.setenv("HOSTED_KCC_CUSTOM_WIDTH", "900")
    monkeypatch.setenv("HOSTED_KCC_OUTPUT_MODE", "suwayomi_local")
    monkeypatch.setenv("HOSTED_KCC_EXTRA_ARGS", '--gamma "1.2" --upscale')

    cfg = load_config(config_path=config_path)

    assert cfg.conversion.custom_width == 900
    assert cfg.output.mode == "suwayomi_local"
    assert cfg.conversion.extra_args == ["--gamma", "1.2", "--upscale"]
    generated = config_path.read_text(encoding="utf-8")
    assert 'custom_width = 900' in generated
    assert 'mode = "suwayomi_local"' in generated


def test_existing_config_is_not_rewritten_when_env_overrides(tmp_path, monkeypatch):
    config_path = tmp_path / "config.toml"
    config_path.write_text('[conversion]\ncustom_width = 700\n', encoding="utf-8")
    monkeypatch.setenv("HOSTED_KCC_CUSTOM_WIDTH", "824")

    before = config_path.read_text(encoding="utf-8")
    cfg = load_config(config_path=config_path)

    assert cfg.conversion.custom_width == 824
    assert config_path.read_text(encoding="utf-8") == before


def test_invalid_output_mode_is_rejected(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text('[output]\nmode = "flat"\n', encoding="utf-8")

    with pytest.raises(ConfigError, match="output.mode"):
        load_config(config_path=config_path)


def test_comma_separated_input_roots_are_parsed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOSTED_KCC_INPUT_ROOTS", "/input,/library/inbox")

    cfg = load_config(config_path=tmp_path / "config.toml")

    assert cfg.paths.input_roots == [Path("/input"), Path("/library/inbox")]
