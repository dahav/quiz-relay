# AGENTS.md

Guide for humans and coding agents in this repository.

## Goal

`quiz-relay` is a local Python CLI for:

1. Taking a screenshot
2. Running AI analysis on the image
3. Validating answers
4. Optionally sending a compact result to ESP32

## Project structure (important)

- `src/quiz_relay/` - application code
- `tests/` - pytest tests
- `config.example.toml` - reference configuration
- `README.md` - user documentation
- `docs/` - additional docs (`gnome_shortcut.md`, `esp32_protocol.md`)

## Quick setup

```bash
cd /path/to/quiz-relay
make setup
cp config.example.toml config.toml
```

## Standard commands

```bash
cd /path/to/quiz-relay
make setup
.venv/bin/quiz-relay --config config.toml config-check
.venv/bin/quiz-relay --config config.toml list-monitors
.venv/bin/quiz-relay --config config.toml test-screenshot
.venv/bin/quiz-relay --config config.toml solve --source cli
make clean
.venv/bin/python -m pytest
```

## Development rules

- Python >= 3.11
- Repository language is English only. Do not create German text in repository content.
- Keep new logic in small, testable functions whenever possible.
- Reuse existing error types from `src/quiz_relay/errors.py`.
- Keep CLI behavior centralized in `src/quiz_relay/cli.py`.
- Do not commit secrets to code or repository.
- Do not make major architecture changes without updating `README.md` and tests.

## Test rules

Before finishing changes, at minimum run:

```bash
cd /path/to/quiz-relay
.venv/bin/python -m pytest
```

For focused changes, at least run the affected tests, for example:

```bash
cd /path/to/quiz-relay
.venv/bin/python -m pytest tests/test_mouse_listener.py
```

## Configuration and ENV

- Configuration file via `--config` or `QUIZ_RELAY_CONFIG`
- Profile via `--profile` or `QUIZ_RELAY_PROFILE`
- Set AI secrets via environment (for example `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`)

## Troubleshooting (common)

### `quiz-relay: command not found`

- Activate venv or use the binary directly:

```bash
source .venv/bin/activate
quiz-relay config-check
```

or

```bash
.venv/bin/quiz-relay config-check
```

### `list-monitors` fails because of missing `mss`

```bash
.venv/bin/python -m pip install -e '.[dev]'
```

### `listen-mouse --scan` does not react

- Global mouse events are implemented for X11/Xorg here.
- Under Wayland, the command exits with a clear error message.

## Change checklist for agents

- Reproduced the problem
- Implemented the smallest possible fix
- Added/updated affected tests
- Ran tests locally
- Updated `README.md` for user-visible behavior/CLI changes
- Avoided unnecessary file or style changes

## Do-Not

- Do not commit API keys, tokens, or private endpoints.
- Do not ship silent behavior changes without docs/tests.
- Do not version manual artifacts (`runtime/`, screenshots, logs).

