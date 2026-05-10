# Quiz Relay Project Notes

This file is a lightweight project note, not a binding architecture specification.

Quiz Relay is intentionally simple:

```text
trigger -> screenshot -> AI analysis -> validated answers -> optional HTTP relay
```

The code avoids framework-style layering. A run is coordinated by `quiz_relay.runner.run_once()`, and the implementation is split only where the runtime behavior is naturally different:

- `capture.py` handles screenshots and monitor listing.
- `ai.py` handles prompts, provider calls, response parsing, and validation.
- `relay.py` handles payload mapping and HTTP delivery.
- `mouse.py` handles mouse events.
- `models.py` contains shared dataclasses.
- `config.py` loads TOML and environment-driven settings.
- `cli.py` exposes the user commands.

## Platform Direction

The application should remain usable on Linux, macOS, and Windows where the underlying libraries and OS permissions allow it.

- Screenshot capture uses `mss`, which is available on all three target platforms.
- Mouse listening uses `pynput`; Linux Wayland is expected to block global mouse access, while X11, macOS, and Windows remain target environments.
- Run locking uses atomic lock-file creation instead of `fcntl`, because `fcntl` is not portable to Windows.
- Run logs use the local system timezone and include an explicit UTC offset.

## Non-goals

Quiz Relay is not a GUI, web app, browser extension, or receiver service. It only captures an image, asks an AI provider for structured answers, validates the result, logs the run, and optionally sends a compact payload to an HTTP endpoint.
