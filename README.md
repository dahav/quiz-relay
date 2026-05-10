# Quiz Relay

Quiz Relay is a small local CLI that runs one direct flow:

```text
trigger -> screenshot -> AI analysis -> validated answers -> optional HTTP relay
```

The internals are intentionally flat. The main modules are:

- `runner.py`: coordinates one run.
- `capture.py`: captures screenshots with `mss` and lists monitors.
- `ai.py`: builds the prompt, calls OpenAI or Anthropic, parses and validates the response.
- `relay.py`: builds and sends the optional HTTP payload.
- `mouse.py`: listens for mouse events through `pynput`.
- `models.py`: shared dataclasses.
- `cli.py`: command-line interface.

## Requirements

- Python 3.11+
- `make`
- A desktop session that allows screenshots
- API key in the environment, for example `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`

Screenshot capture uses `mss`, which supports Linux, macOS, and Windows. Platform permissions still apply. On macOS, screen recording permission may be required. On Windows, desktop capture must be allowed for the running user.

Mouse listening uses `pynput`. Linux Wayland sessions usually block global mouse events, so `listen-mouse` exits with a clear error there. X11, macOS, and Windows are kept as supported targets, subject to OS accessibility/privacy permissions.

## Quickstart

```bash
cd /path/to/quiz-relay
make setup
cp config.example.toml config.toml
```

Run initial checks:

```bash
.venv/bin/quiz-relay --config config.toml config-check
.venv/bin/quiz-relay --config config.toml list-monitors
.venv/bin/quiz-relay --config config.toml test-screenshot
```

Run one full cycle:

```bash
.venv/bin/quiz-relay --config config.toml solve --source cli
```

## Configuration

Example configuration: `config.example.toml`

Sections:

- `[app]`: profile, runtime directory, run lock behavior, raw AI response logging.
- `[screenshot]`: PNG format, monitor index, optional capture delay.
- `[ai]`: provider, model, timeout, response language, prompt file.
- `[http_relay]`: enable flag, URL, mode, timeout, retries.
- `[http_relay.fields]`: optional outgoing payload mapping.
- `[mouse]`: default mouse event.
- `[logging]`: JSONL run log path.

Configuration can be selected with `--config /path/to/config.toml` or `QUIZ_RELAY_CONFIG`. The profile can be selected with `--profile` or `QUIZ_RELAY_PROFILE`.

## Commands

```bash
quiz-relay config-check
quiz-relay doctor
quiz-relay list-monitors
quiz-relay test-screenshot
quiz-relay solve --source cli
quiz-relay solve --source shortcut
quiz-relay solve --test-image /path/to/image.png --no-relay
quiz-relay listen-mouse --list-events
quiz-relay listen-mouse --scan
quiz-relay listen-mouse --event middle-click
quiz-relay test-relay --source test
quiz-relay parse-response /path/to/response.txt
```

## HTTP Relay

`[http_relay].mode` controls transport:

- `json`: send a POST request with a JSON body.
- `query`: send a GET request with mapped values as query parameters.

Configure `[http_relay.fields]` to map outgoing field names to expressions such as `context.task_id`, `solution.answers`, `solution.answers_text`, `solution.explanation`, or `solution.confidence`.

## Runtime Data

Default paths:

- Screenshots: `runtime/screenshots/`
- Run log: `runtime/logs/runs.jsonl`
- Lock file while a run is active: `runtime/quiz-relay.lock`

Run log timestamps use the local system timezone and include the UTC offset, for example `2026-05-07T16:33:26.381+02:00`.

## Development

```bash
make setup
.venv/bin/python -m pytest
```

Run one focused test:

```bash
.venv/bin/python -m pytest tests/test_mouse_listener.py
```

`make clean` removes Python cache files, test/build artifacts, egg-info directories, coverage output, and `runtime/`.

## Additional Docs

- `docs/gnome_shortcut.md`
- `docs/http_relay.md`
- `spec.md`
