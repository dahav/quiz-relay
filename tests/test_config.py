from pathlib import Path

from quiz_relay.config import load_settings


def test_loads_defaults_without_config():
    settings = load_settings(None)
    assert settings.app.name == "Quiz Relay"
    assert settings.screenshot.monitor == 1
    assert settings.http_relay.enabled is False


def test_loads_toml_config(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("QUIZ_RELAY_PROFILE", "")
    config = tmp_path / "config.toml"
    config.write_text(
        """
[app]
profile = "local"

[screenshot]
monitor = 2

[ai]
provider = "anthropic"

[http_relay]
enabled = true
mode = "query"

[http_relay.fields]
answer = "solution.answers_text"
""",
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.app.profile == "local"
    assert settings.screenshot.monitor == 2
    assert settings.ai.provider == "anthropic"
    assert settings.http_relay.enabled is True
    assert settings.http_relay.mode == "query"
    assert settings.http_relay.fields == {"answer": "solution.answers_text"}
