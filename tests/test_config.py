from pathlib import Path

from quiz_relay.config import load_settings


def test_loads_defaults_without_config():
    settings = load_settings(None)
    assert settings.app.name == "Quiz Relay"
    assert settings.screenshot.backend == "mss"
    assert settings.esp32.enabled is False


def test_loads_toml_config(tmp_path: Path):
    config = tmp_path / "config.toml"
    config.write_text(
        """
[app]
profile = "local"

[screenshot]
monitor = 2

[ai]
provider = "anthropic"

[esp32]
enabled = true
""",
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.app.profile == "local"
    assert settings.screenshot.monitor == 2
    assert settings.ai.provider == "anthropic"
    assert settings.esp32.enabled is True
