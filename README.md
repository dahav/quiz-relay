# Quiz Relay

Local CLI that screenshots, asks an AI for the answer, and optionally pings a vibration endpoint.

```
trigger -> screenshot -> AI -> JSON -> HTTP GET
```

## Setup

```bash
make setup
cp config.example.toml config.toml
# put OPENAI_API_KEY or ANTHROPIC_API_KEY in .env
```

## Run

```bash
.venv/bin/quiz-relay solve                 # one cycle
.venv/bin/quiz-relay listen                # trigger on each mouse event from config
.venv/bin/quiz-relay listen --event scroll-up
.venv/bin/quiz-relay listen --scan         # print every detected event
.venv/bin/quiz-relay listen --list-events  # list supported events
```

## Config

`config.toml` next to the CWD, or set `QUIZ_RELAY_CONFIG=/path/to/config.toml`.

The relay sends a GET request with `on`, `off`, `pause`, `duty` plus either
`n` (single answer, e.g. `A` -> `1`) or `seq` (multiple answers, e.g. `1,3`).

## Notes

- Screenshot capture uses `mss`. macOS may require screen-recording permission.
- Mouse listening uses `pynput`. Wayland blocks global mouse events; X11/macOS/Windows work.
- Screenshots land in `runtime/screenshots/`.
