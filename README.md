# Quiz Relay

Local CLI that screenshots, asks an AI for the answer, and optionally pings a vibration endpoint.

```
trigger -> screenshot -> AI (per mode) -> Solution -> relay module(s)
```

## Setup

```bash
make setup
cp config.example.toml config.toml
# set openai_api_key in config.toml [ai]
```

## Run

```bash
.venv/bin/quiz-relay solve --mode istqb
.venv/bin/quiz-relay solve --mode istqb --image temp/sample.png   # skip screenshot, use file
.venv/bin/quiz-relay solve --mode istqb --relay http
.venv/bin/quiz-relay solve --mode istqb --relay http --relay keyboard_led
.venv/bin/quiz-relay listen --mode iso27001 --relay keyboard_led
.venv/bin/quiz-relay listen --mode istqb --event scroll-up
.venv/bin/quiz-relay listen --scan         # show every detected event
.venv/bin/quiz-relay listen --list-events  # list supported events
.venv/bin/quiz-relay modes                 # list available prompt modes
.venv/bin/quiz-relay relays                # list available relay modules
```

`--mode` is required. `--relay` is optional and may be repeated.

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

## Relays

Relay modules live in `src/quiz_relay/relays/`. Each `.py` file in that
directory that defines a `Relay` subclass with a `name` is auto-discovered.
Add a new module by dropping a file in there — no other code change needed.

Selection happens on the command line with `--relay <name>` (repeat for
multiple). Each module reads its own `[relay.<name>]` TOML section.

Built-in modules:

- `http`: GET to a URL with `on`, `off`, `pause`, `duty` plus either `n`
  (single answer, e.g. `A` -> `1`) or `seq` (multiple answers, e.g. `1,3`).
- `keyboard_led`: blinks a lock LED under `/sys/class/leds/<device>/`. The
  number of pulses encodes the answer (`A` / `1` -> 1 pulse, `B` / `2` -> 2,
  …). Multiple answers are separated by `pause`.

Both relays share the same timing keys (`on`, `off`, `pause` in ms) so the
LED blink cadence matches what the HTTP endpoint plays. Keep the values
in sync across `[relay.http]` and `[relay.keyboard_led]` if you change
them.

### Keyboard LED permissions

Writing `/sys/class/leds/*/brightness` is normally root-only. The shipped
udev rule grants write access to members of the `input` group. Install it
once and add yourself to the group:

```bash
sudo cp udev/99-quiz-relay-leds.rules /etc/udev/rules.d/
sudo usermod -aG input "$USER"
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=leds --action=add
```

Then log out and back in (or reboot) so the new group membership is active
in your shell. Verify — `brightness` should be owned by `root:input` with
mode `0664`, and `input` should appear in `groups`:

```bash
ls -l /sys/class/leds/input*::*lock/brightness
groups | tr ' ' '\n' | grep -x input
```

Why `input` and not e.g. `plugdev`: the lock LEDs belong to keyboard input
devices, and `input` is the conventional group for raw input device access
on Debian/Ubuntu/Arch. The udev rule explicitly chgrp's `brightness` to
this group, so the user running quiz-relay must be a member.

Why the rule uses `RUN+=` instead of `GROUP="input", MODE="0664"`: for the
`leds` subsystem, udev's `GROUP=`/`MODE=` apply only to the device node
itself and do **not** propagate to sysfs attribute files like
`brightness`. The shipped rule therefore calls `chgrp input` and
`chmod 0664` on `brightness` explicitly inside `RUN+=`.

Notes:

- `udevadm trigger` without `--action=add` does not re-fire the `RUN+=`
  hook for LEDs that already existed at boot, so the plain trigger is not
  enough.
- `usermod -aG input` only takes effect for new login sessions. `newgrp
  input` switches the current shell into the group as a workaround.
- One-off fallback if `udevadm trigger` doesn't pick up existing LEDs:
  `sudo chgrp input /sys/class/leds/input*::*lock/brightness && sudo chmod 0664 /sys/class/leds/input*::*lock/brightness`.
  The udev rule then takes over from the next boot.

Pick a device that exists on your system:

```bash
ls /sys/class/leds/
```

Common candidates: `input3::capslock`, `input3::scrolllock`,
`input3::numlock` (the `inputN` prefix varies per kernel boot).

Smoke-test the wiring without solving anything:

```bash
.venv/bin/quiz-relay relay-test --relay keyboard_led
.venv/bin/quiz-relay relay-test --relay http
```

Sends a fixed 3-pulse signal through the selected relay(s). Exit code is
0 only if every relay reports `sent: true`.

## Notes

- Screenshot capture uses `mss`. macOS may require screen-recording permission.
- Wayland: `mss` returns black images. Switch to an X11 session.
  The pre-check aborts before the AI call if the screenshot looks empty.
- Mouse listening uses `pynput`. Wayland blocks global mouse events.
- Screenshots land in `runtime/screenshots/`.
