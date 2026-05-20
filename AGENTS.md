# Repository Guidelines

## Project Structure & Module Organization

This is a Python 3.11 package using a `src/` layout. Application code lives in `src/quiz_relay/`: `cli.py` defines the `quiz-relay` command, `core.py` coordinates screenshot solving, `config.py` loads TOML settings, `solution.py` models answer output, and `mouse.py` handles trigger events. Relay implementations live in `src/quiz_relay/relays/`; add new relay modules there and register them in `relays/__init__.py`. Prompt modes are Markdown files in `prompts/`; `multiplechoice.md` is shared base guidance and is not a selectable mode. System integration files live in `udev/`. Runtime screenshots are written under `runtime/screenshots/`.

## Build, Test, and Development Commands

- `make setup`: create `.venv` and install the package editable with its runtime dependencies.
- `.venv/bin/quiz-relay modes`: verify prompt discovery.
- `.venv/bin/quiz-relay relays`: verify relay registration.
- `.venv/bin/quiz-relay solve --mode istqb --image temp/sample.png`: run the solver against an existing image without taking a screenshot.
- `.venv/bin/quiz-relay relay-test --relay keyboard_led`: send a fixed three-pulse relay signal.
- `make clean`: remove Python caches, build artifacts, coverage output, and `runtime/`.

## Coding Style & Naming Conventions

Use standard Python style with 4-space indentation, type annotations for public functions, and small modules with explicit responsibilities. Follow existing names: relay names use lowercase snake case such as `keyboard_led`, prompt modes use lowercase file stems such as `istqb.md`, and CLI subcommands use kebab case where needed. Keep mode files focused on domain rules; do not override the JSON output schema in prompts.

## Testing Guidelines

There is no committed test suite yet. When adding tests, place them under `tests/` and name files `test_<module>.py`. Prefer focused unit tests for parsing, configuration, `answers_to_pulses`, relay result handling, and CLI argument behavior. For hardware or network behavior, keep tests isolated with fakes rather than requiring real LED devices, mouse hooks, screenshots, or HTTP endpoints.

## Commit & Pull Request Guidelines

Recent commits use short lowercase summaries such as `support any led`, `simplify`, and `refactoring`. Keep subjects concise and imperative or descriptive. Pull requests should explain the behavior change, list manual verification commands, mention config or udev changes, and include screenshots or sample JSON output when CLI-visible behavior changes.

## Security & Configuration Tips

Do not commit `config.toml` with real API keys; start from `config.example.toml`. Treat screenshots in `runtime/` as potentially sensitive. Changes to `udev/` affect local device permissions, so document installation and rollback steps when modifying rules.
