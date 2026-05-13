# Quiz Relay

Local CLI that screenshots, asks an AI for the answer, and optionally pings a vibration endpoint.

```
trigger -> screenshot -> AI (per mode) -> JSON -> HTTP GET
```

## Setup

```bash
make setup
cp config.example.toml config.toml
# set openai_api_key (or anthropic_api_key) in config.toml [ai]
```

## Run

```bash
.venv/bin/quiz-relay solve --mode istqb
.venv/bin/quiz-relay listen --mode iso27001
.venv/bin/quiz-relay listen --mode istqb --event scroll-up
.venv/bin/quiz-relay listen --scan         # show every detected event
.venv/bin/quiz-relay listen --list-events  # list supported events
.venv/bin/quiz-relay modes                 # list available prompt modes
```

`--mode` is required.

## Modes

A mode is a markdown file in `prompts/<name>.md` containing domain rules
(e.g. ISTQB exam logic, Führerschein-Theorie, ISO27001 audit).
The file is appended to the base prompt as "Additional instructions".
Drop a new file into `prompts/` to add a mode — no code change needed.

Mode files must contain only domain rules. The JSON output schema is
controlled by the base prompt; do not override the output format in a mode file.

`prompts/multiplechoice.md` is a reserved common base: if present, its
content is automatically included as "Common instructions" alongside the
selected mode. Keep generic multiple-choice procedure there; keep only
topic-specific knowledge in each mode file. The base is not selectable
via `--mode`.

## Config

`config.toml` next to the CWD, or pass `--config /path/to/config.toml`.

The relay sends a GET request with `on`, `off`, `pause`, `duty` plus either
`n` (single answer, e.g. `A` -> `1`) or `seq` (multiple answers, e.g. `1,3`).

## Notes

- Screenshot capture uses `mss`. macOS may require screen-recording permission.
- Wayland: `mss` returns black images. Switch to an X11 session.
  The pre-check aborts before the AI call if the screenshot looks empty.
- Mouse listening uses `pynput`. Wayland blocks global mouse events.
- Screenshots land in `runtime/screenshots/`.
