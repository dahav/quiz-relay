import json
from argparse import Namespace

from quiz_relay.cli import _settings_from_args, cmd_test_relay


def test_cli_uses_local_config_toml_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QUIZ_RELAY_CONFIG", "")
    (tmp_path / "config.toml").write_text(
        """
[http_relay]
enabled = true
url = "http://example.test/vibe"
mode = "query"
""",
        encoding="utf-8",
    )

    settings = _settings_from_args(Namespace(config=None, profile=None, no_relay=False))

    assert settings.config_path.name == "config.toml"
    assert settings.http_relay.enabled is True
    assert settings.http_relay.url == "http://example.test/vibe"


def test_cli_preserves_env_config_precedence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.toml").write_text(
        """
[http_relay]
enabled = true
url = "http://local.test/vibe"
""",
        encoding="utf-8",
    )
    env_config = tmp_path / "env-config.toml"
    env_config.write_text(
        """
[http_relay]
enabled = true
url = "http://env.test/vibe"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("QUIZ_RELAY_CONFIG", str(env_config))

    settings = _settings_from_args(Namespace(config=None, profile=None, no_relay=False))

    assert settings.config_path == env_config
    assert settings.http_relay.url == "http://env.test/vibe"


def test_test_relay_fails_when_relay_is_disabled(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QUIZ_RELAY_CONFIG", "")

    exit_code = cmd_test_relay(Namespace(config=None, profile=None, source="test"))

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 6
    assert output["status"] == "failed"
    assert output["sent"] is False
    assert output["error"] == "disabled"
