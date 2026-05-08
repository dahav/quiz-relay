# Quiz Relay

Quiz Relay is a local CLI tool that analyzes multiple-choice questions from screenshots and can optionally send the result to an ESP32-compatible HTTP endpoint.

Core flow:

```text
Trigger -> Screenshot -> AI analysis -> JSON solution -> optional ESP32 POST
```

## What this project does

- Capture screenshots and list monitor information (`mss` backend)
- Analyze images and solve quizzes using OpenAI or Anthropic
- Parse and validate AI responses into a compact answer format
- Log results locally
- Optionally send a compact payload to ESP32
- Trigger via CLI, one-shot shortcut run, or mouse listener

## Requirements

- Linux desktop session for screenshot features
- Python 3.11+
- For global mouse events (`listen-mouse`): currently X11/Xorg only (Wayland exits with a clear error message)

## Quickstart

```bash
cd /home/dahav/Privat/dev/quiz-relay
python3 -m venv .venv
.venv/bin/python -m pip install -e .[dev]
cp config.example.toml config.toml
```

Optional: set API keys in `.env` (or your shell), for example `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`.

Initial checks:

```bash
cd /home/dahav/Privat/dev/quiz-relay
.venv/bin/quiz-relay config-check --config config.toml
.venv/bin/quiz-relay list-monitors --config config.toml
.venv/bin/quiz-relay test-screenshot --config config.toml
```

## Configuration

Example configuration: `config.example.toml`

Important sections:

- `[app]`: runtime directory and general runtime behavior
- `[screenshot]`: backend, monitor index, delay
- `[ai]`: provider (`openai`/`anthropic`), model, timeout, prompt file
- `[esp32]`: enable flag, URL, endpoint, timeout, retries
- `[mouse_trigger]`: default mouse event
- `[logging]`: log and runs files

Selecting configuration:

- via CLI: `--config /path/to/config.toml`
- via ENV: `QUIZ_RELAY_CONFIG=/path/to/config.toml`
- profile via `--profile` or `QUIZ_RELAY_PROFILE`

## CLI commands

### Diagnostics and setup

```bash
quiz-relay config-check
quiz-relay doctor
quiz-relay list-monitors
quiz-relay test-screenshot
```

### Run pipeline

```bash
quiz-relay solve --source cli
quiz-relay solve --source shortcut
quiz-relay solve --test-image examfit/test.png --no-esp32
```

### Mouse listener

```bash
quiz-relay listen-mouse --list-events
quiz-relay listen-mouse --scan
quiz-relay listen-mouse --event middle-click
```

### ESP32 test

```bash
quiz-relay test-esp --source test
```

## Common issues and fixes

### `quiz-relay: command not found`

Use the venv binary directly or activate the venv:

```bash
cd /home/dahav/Privat/dev/quiz-relay
source .venv/bin/activate
quiz-relay config-check
```

Or directly:

```bash
cd /home/dahav/Privat/dev/quiz-relay
.venv/bin/quiz-relay config-check
```

### `list-monitors` reports missing `mss`

```bash
cd /home/dahav/Privat/dev/quiz-relay
.venv/bin/python -m pip install -e .[dev]
```

### `listen-mouse --scan` does not react / exits with TriggerError

`pynput`-based global mouse events are intentionally limited to X11 here. Under Wayland, the command exits with a clear hint. Switch to an X11/Xorg session for this command.

## Output and runtime data

Default paths (configurable in `config.toml`):

- Screenshots: `runtime/screenshots/`
- Run-Logs: `runtime/logs/runs.jsonl`
- App-Logs: `runtime/logs/app.log`
- Error logs: `runtime/logs/errors.log`

## Development

Run all tests:

```bash
cd /home/dahav/Privat/dev/quiz-relay
.venv/bin/python -m pytest
```

Run a single test:

```bash
cd /home/dahav/Privat/dev/quiz-relay
.venv/bin/python -m pytest tests/test_mouse_listener.py
```

## Additional docs

- `docs/gnome_shortcut.md`
- `docs/esp32_protocol.md`
- `spec.md`
