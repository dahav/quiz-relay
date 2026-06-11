# Quiz Relay

Local CLI and FastAPI service that screenshots or accepts uploaded quiz images, asks an AI for the answer, and optionally dispatches relay signals.

```
CLI/API -> screenshot or upload -> AI (per mode) -> Solution -> relay module(s)
```

## Architecture

Transport wrappers are intentionally thin:

- `src/quiz_relay/cli.py`: parses command-line arguments, loads config, calls app use-cases, and prints results.
- `src/quiz_relay/web.py`: exposes FastAPI routes, checks API keys, stores uploads, maps application errors to HTTP responses, and returns JSON.
- `src/quiz_relay/app.py`: orchestrates solve and relay-test use-cases shared by CLI and API.
- `src/quiz_relay/service.py`: validates images, calls the AI/parser path, builds solution payloads, and dispatches relays.
- `src/quiz_relay/core.py`: owns prompt loading, screenshot capture, OpenAI calls, and response parsing.
- `src/quiz_relay/uploads.py`: validates and retains raw API image uploads.

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
.venv/bin/quiz-relay listen --mode togaf --relay keyboard_led
.venv/bin/quiz-relay listen --mode istqb --event scroll-up
.venv/bin/quiz-relay listen --scan         # show every detected event
.venv/bin/quiz-relay listen --list-events  # list supported events
.venv/bin/quiz-relay modes                 # list available prompt modes
.venv/bin/quiz-relay relays                # list available relay modules
.venv/bin/quiz-relay scan-leds             # list keyboard LED device names
.venv/bin/quiz-relay --config /path/to/config.toml modes
```

`--mode` is required. `--relay` is optional and may be repeated.


## Web API

The API is a FastAPI app served by `uvicorn`. For local development, run it directly from the virtualenv; nginx is only needed for VPS deployment:

```bash
.venv/bin/uvicorn quiz_relay.web:app --reload --host 127.0.0.1 --port 8000
```

Open the interactive API docs at `http://127.0.0.1:8000/docs`.

Configure `[api].keys` in `config.toml`; clients must send one value as `X-API-Key`. Uploads are raw image bodies and are retained in `[api].upload_dir`:

```bash
curl -X POST \
  -H "X-API-Key: change-me" \
  -H "Content-Type: image/jpeg" \
  --data-binary @question.jpg \
  http://127.0.0.1:8000/solve/istqb
```

Optional relays can be triggered with repeated query parameters, for example `/solve/istqb?relay=http&relay=keyboard_led`. The response includes `solution`, `answer_ids`, `pulses`, the retained `image` path, and optional `relays` results.

Smoke-test the API without calling OpenAI:

```bash
curl http://127.0.0.1:8000/health

curl -H "X-API-Key: change-me" \
  http://127.0.0.1:8000/modes

curl -X POST \
  -H "X-API-Key: change-me" \
  -H "Content-Type: text/plain" \
  --data-binary "x" \
  http://127.0.0.1:8000/solve/istqb
```

The last command should return HTTP 400 because `text/plain` is not an allowed image type; it verifies routing, auth, and validation without using the OpenAI API.

### VPS deployment behind nginx

On a headless VPS the screenshot and `keyboard_led` relays do not work (no
display, no LED). Use the upload path (`POST /solve/<mode>` with an image body)
and optionally the `http` relay.

#### 1. Get the code onto the VPS

```bash
sudo mkdir -p /opt/quiz-relay
sudo chown "$USER:$USER" /opt/quiz-relay
git clone <your-repo> /opt/quiz-relay   # or rsync/scp
cd /opt/quiz-relay
```

#### 2. Build the virtualenv on the server

Build `.venv` **on the VPS**, never copy it from another machine. The venv
shebangs and the editable install are pinned to their build path, so a copied
`.venv` breaks with `bad interpreter` / `No module named 'quiz_relay'`.

```bash
sudo apt install -y python3-venv python3-pip
make setup
```

#### 3. Configure

```bash
cp config.example.toml config.toml
```

- Set `[ai].openai_api_key` (never commit it).
- Replace `[api].keys` with a long random value:
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- Keep `[api].max_upload_bytes` aligned with the nginx `client_max_body_size`.

#### 4. systemd service (uvicorn on localhost only)

`/etc/systemd/system/quiz-relay.service`:

```ini
[Unit]
Description=Quiz Relay API
After=network.target

[Service]
WorkingDirectory=/opt/quiz-relay
Environment=QUIZ_RELAY_CONFIG=/opt/quiz-relay/config.toml
ExecStart=/opt/quiz-relay/.venv/bin/uvicorn quiz_relay.web:app --host 127.0.0.1 --port 8000
Restart=always
User=www-data
Group=www-data

[Install]
WantedBy=multi-user.target
```

The service user must be able to write `runtime/uploads`:

```bash
sudo chown -R www-data:www-data /opt/quiz-relay
sudo systemctl daemon-reload
sudo systemctl enable --now quiz-relay
sudo systemctl status quiz-relay
```

The service is independent of nginx; uvicorn only listens on `127.0.0.1:8000`
and nginx terminates TLS in front of it.

#### 5. Rate-limit zone (once)

Each public request may call the OpenAI API, so rate-limit it. Add inside the
`http { ... }` block of `/etc/nginx/nginx.conf`:

```nginx
limit_req_zone $binary_remote_addr zone=quiz:10m rate=10r/m;
```

#### 6a. nginx — own subdomain (recommended)

A dedicated `server` block keeps logs, TLS, and `/docs` clean:

```nginx
server {
    server_name quiz.example.com;
    client_max_body_size 10M;          # = [api].max_upload_bytes

    location / {
        limit_req zone=quiz burst=5 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 130s;        # > [ai].timeout_seconds
    }
}
```

Then issue a certificate:

```bash
sudo certbot --nginx -d quiz.example.com
```

#### 6b. nginx — sub-path on an existing domain

To avoid a new subdomain, add a `location` to an existing TLS `server` block,
**before** its `location /`. The trailing slash on `proxy_pass` strips the
`/quiz` prefix so FastAPI still sees `/health`, `/modes`, `/solve/...`:

```nginx
    location /quiz/ {
        limit_req zone=quiz burst=5 nodelay;
        client_max_body_size 10M;       # overrides a smaller server-level limit
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 130s;
    }
```

Note: `/quiz/docs` (Swagger UI) may fail to load its assets under a sub-path
because of absolute URLs. For pure API use this does not matter; if you need the
docs, prefer the subdomain in 6a.

#### 7. Apply and test

```bash
sudo nginx -t && sudo systemctl reload nginx

curl https://quiz.example.com/health
curl -H "X-API-Key: <key>" https://quiz.example.com/modes
curl -X POST -H "X-API-Key: <key>" \
  -H "Content-Type: image/jpeg" \
  --data-binary @question.jpg \
  https://quiz.example.com/solve/istqb
```

For the sub-path variant the URLs are `https://example.com/quiz/health`, etc.

#### Security checklist

- Never commit `config.toml` with a real OpenAI key or `[api].keys`.
- Firewall: expose only 80/443; keep port 8000 bound to `127.0.0.1`.
- Keep the rate limit enabled (every call costs OpenAI tokens).
- `runtime/uploads` retains uploaded images; prune it periodically as it may be
  sensitive.

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

`config.toml` next to the CWD, or pass `--config /path/to/config.toml`
before the subcommand.

## Relays

Relay modules live in `src/quiz_relay/relays/` and are registered in
`src/quiz_relay/relays/__init__.py`.

Selection happens on the command line with `--relay <name>` (repeat for
multiple). Each module reads its own `[relay.<name>]` TOML section.

Built-in relays:

- `http`: GET to a URL with `on`, `off`, `pause`, `duty` and `seq`
  (answer pulses, e.g. `A,C` -> `1,3`).
- `keyboard_led`: blinks a lock LED under `/sys/class/leds/<device>/`. The
  number of pulses encodes the answer (`A` / `1` -> 1 pulse, `B` / `2` -> 2,
  …). Multiple answers are separated by `pause`. This relay requires an
  explicit `device` value in `config.toml`.

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

### Keyboard LED device selection

There is no automatic LED selection. The `inputN` prefix is assigned by the
kernel and can vary between machines and boots. Scan the available lock LEDs
first:

```bash
.venv/bin/quiz-relay scan-leds
```

The output includes copyable config lines:

```text
config: device = "input4::capslock"
```

Paste one of those values into `[relay.keyboard_led]`:

```toml
[relay.keyboard_led]
device = "input4::capslock"
on = 300
off = 200
pause = 800
max_pulses = 9
```

If the relay reports `LED device not found`, run `scan-leds` again and update
the configured device.

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
