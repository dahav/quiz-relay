# GNOME Shortcut

Quiz Relay does not register global keyboard shortcuts itself. Configure the shortcut in GNOME and point it at the one-shot CLI command.

1. Open GNOME Settings.
2. Open Keyboard Shortcuts.
3. Create a custom shortcut.
4. Enter this command:

```bash
/home/<user>/.local/bin/quiz-relay --config /path/to/config.toml solve --source shortcut
```

5. Assign the shortcut, for example `Alt+F9`.
6. Run the shortcut once and check `runtime/logs/runs.jsonl`.

Use the virtualenv binary directly if the console script is not installed globally:

```bash
/path/to/quiz-relay/.venv/bin/quiz-relay --config /path/to/quiz-relay/config.toml solve --source shortcut
```
