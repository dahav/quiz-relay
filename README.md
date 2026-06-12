# Quiz Relay

Quiz Relay ist ein lokales Python-Tool, das Quiz- oder Prüfungsfragen als
Screenshot bzw. Bilddatei an OpenAI sendet, die Antwort auswertet und optional
ein Relay-Signal auslöst.

```text
Screenshot/Upload -> AI-Auswertung -> JSON-Ergebnis -> optionales Relay
```

## Setup

Voraussetzung: Python 3.11 oder neuer.

```bash
make setup
cp config.example.toml config.toml
```

Danach in `config.toml` mindestens `[ai].openai_api_key` setzen.

Nützliche Checks:

```bash
.venv/bin/quiz-relay modes
.venv/bin/quiz-relay relays
```

## CLI

Ein Bild auswerten:

```bash
.venv/bin/quiz-relay solve --mode istqb --image question.png
```

Screenshot des konfigurierten Monitors auswerten:

```bash
.venv/bin/quiz-relay solve --mode istqb
```

Mit Relay:

```bash
.venv/bin/quiz-relay solve --mode istqb --relay http
.venv/bin/quiz-relay solve --mode istqb --relay http --relay keyboard_led
```

Auf ein Mausereignis warten und dann auswerten:

```bash
.venv/bin/quiz-relay listen --mode istqb --relay keyboard_led
.venv/bin/quiz-relay listen --scan
.venv/bin/quiz-relay listen --list-events
```

`--mode` ist bei `solve` und normalem `listen` Pflicht. `--relay` ist optional
und kann mehrfach angegeben werden.

## Web API

Server lokal starten:

```bash
.venv/bin/uvicorn quiz_relay.web:app --reload --host 127.0.0.1 --port 8000
```

API-Dokumentation:

```text
http://127.0.0.1:8000/docs
```

`[api].keys` in `config.toml` konfigurieren. Clients senden einen dieser Werte
als `X-API-Key`.

Smoke-Test ohne OpenAI-Aufruf:

```bash
curl http://127.0.0.1:8000/health
curl -H "X-API-Key: change-me" http://127.0.0.1:8000/modes
```

Bild auswerten:

```bash
curl -X POST \
  -H "X-API-Key: change-me" \
  -H "Content-Type: image/jpeg" \
  --data-binary @question.jpg \
  http://127.0.0.1:8000/solve/istqb
```

Relay per API:

```bash
curl -X POST \
  -H "X-API-Key: change-me" \
  -H "Content-Type: image/jpeg" \
  --data-binary @question.jpg \
  "http://127.0.0.1:8000/solve/istqb?relay=http&relay=keyboard_led"
```

Uploads werden unter `[api].upload_dir` gespeichert.

## Modi

Modi liegen als Markdown-Dateien in `prompts/`.

- `prompts/istqb.md` ergibt `--mode istqb`
- `prompts/togaf.md` ergibt `--mode togaf`
- `prompts/multiplechoice.md` ist die gemeinsame Basis und nicht direkt
  auswählbar

Neue Modi werden durch eine neue Datei `prompts/<name>.md` ergänzt. Mode-Dateien
sollten nur fachliche Regeln enthalten; das JSON-Format wird vom Basis-Prompt
gesteuert.

## Relays

Verfügbare Relays:

```bash
.venv/bin/quiz-relay relays
```

Einen festen 3-Pulse-Test senden:

```bash
.venv/bin/quiz-relay relay-test --relay http
.venv/bin/quiz-relay relay-test --relay keyboard_led
```

### `http`

Sendet einen GET-Request an die in `[relay.http].url` konfigurierte Adresse.
Timing-Werte wie `on`, `off`, `pause` und `duty` kommen aus `config.toml`.

### `keyboard_led`

Blinkt eine Tastatur-LED unter `/sys/class/leds/...`. Zuerst ein passendes Gerät
finden:

```bash
.venv/bin/quiz-relay scan-leds
```

Die ausgegebene Zeile `config: device = "..."` in `[relay.keyboard_led]`
eintragen.

Falls der Benutzer keine Schreibrechte auf `brightness` hat, die udev-Regel
installieren und neu einloggen:

```bash
sudo cp udev/99-quiz-relay-leds.rules /etc/udev/rules.d/
sudo usermod -aG input "$USER"
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=leds --action=add
```

## Konfiguration

Standardmäßig wird `./config.toml` gelesen. Alternativ:

```bash
.venv/bin/quiz-relay --config /path/to/config.toml modes
```

Wichtige Bereiche:

- `[ai]`: Modell, Timeout, Antwortsprache, OpenAI API-Key
- `[screenshot]`: Monitor für lokale Screenshots
- `[api]`: API-Keys, Upload-Verzeichnis, maximale Upload-Größe
- `[mouse]`: Standardereignis für `listen`
- `[relay.<name>]`: Einstellungen je Relay

## Betriebshinweise

- `config.toml`, Screenshots und Uploads können sensible Daten enthalten.
- Screenshots liegen in `runtime/screenshots/`, API-Uploads in
  `runtime/uploads/`.
- Wayland kann Screenshots oder globale Mausereignisse blockieren.
  Eine X11-Session ist zuverlässiger.
- Auf einem Server ohne Display funktionieren Screenshot und `keyboard_led` in
  der Regel nicht. Dort die Web API mit Bild-Uploads und optional `http`-Relay
  verwenden.
- Für öffentliche Deployments uvicorn nur lokal binden und davor TLS,
  Upload-Limits und Rate-Limiting konfigurieren.

## Projektstruktur

```text
src/quiz_relay/
  cli.py          CLI
  web.py          FastAPI-App
  app.py          gemeinsame Use-Cases
  service.py      Bildprüfung, AI-Aufruf, Relay-Versand
  core.py         Prompts, OpenAI, Parsing, Screenshots
  uploads.py      API-Uploads
  relays/         Relay-Module
prompts/          Prompt-Modi
runtime/          lokale Laufzeitdaten
```
