# Repository Guidelines

## Project Structure & Module Organization

This Python 3.11 package uses a `src/` layout. Application code lives in `src/quiz_relay/`: `cli.py` and `web.py` are thin transport wrappers, `app.py` orchestrates shared use-cases, `service.py` holds shared image-solving and relay behavior, `core.py` handles prompts/OpenAI/parsing, `uploads.py` retains API uploads, `debug.py` centralizes debug output, `config.py` loads TOML, and `errors.py` defines expected errors plus HTTP status mapping. Relays live in `src/quiz_relay/relays/`; add modules there and register them in `relays/__init__.py`. Prompt modes are Markdown files in `prompts/`; `multiplechoice.md` is shared base guidance. Runtime screenshots and uploads are written under `runtime/`.

## Build, Test, and Development Commands

- `make setup`: create `.venv` and install the package editable with its runtime dependencies.
- `.venv/bin/quiz-relay modes`: verify prompt discovery.
- `.venv/bin/quiz-relay relays`: verify relay registration.
- `.venv/bin/quiz-relay relay-test --relay keyboard_led`: send a fixed three-pulse relay signal.
- `.venv/bin/uvicorn quiz_relay.web:app --reload --host 127.0.0.1 --port 8000`: run the local API server.
- `curl -H "X-API-Key: change-me" http://127.0.0.1:8000/modes`: smoke-test API auth and mode discovery without an OpenAI call.
- `make clean`: remove Python caches, build artifacts, coverage output, and `runtime/`.

## Coding Style & Naming Conventions

Use standard Python style with 4-space indentation, type annotations for public functions, and small modules. Keep transport concerns in `cli.py` or `web.py`; shared orchestration belongs in `app.py`, domain helpers in `service.py`, uploads in `uploads.py`, and debug output in `debug.py`. Relay names use snake case such as `keyboard_led`, prompt modes use lowercase file stems such as `istqb.md`, and CLI subcommands use kebab case. Keep mode files focused on domain rules; do not override the JSON schema in prompts.

## Testing Guidelines

There is no committed test suite yet. Add tests under `tests/` as `test_<module>.py`. Cover parsing, configuration, `answers_to_pulses`, relay handling, CLI arguments, and FastAPI endpoints via `TestClient`. Mock OpenAI and fake hardware/network behavior instead of requiring LED devices, mouse hooks, screenshots, or HTTP endpoints.

## Commit & Pull Request Guidelines

Recent commits use short lowercase summaries such as `support any led`, `simplify`, and `refactoring`. Keep subjects concise. Pull requests should explain the behavior change, list verification commands, mention config or udev changes, and include sample JSON output when CLI-visible behavior changes.

## Security & Configuration Tips

Do not commit `config.toml` with real OpenAI or `[api].keys`; start from `config.example.toml`. Treat screenshots and retained uploads in `runtime/` as potentially sensitive. Public deployments should run uvicorn behind nginx with TLS, upload limits, and rate limiting. Changes to `udev/` affect local device permissions, so document installation and rollback steps when modifying rules.
