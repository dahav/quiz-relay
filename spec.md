# Spezifikation: Quiz Relay

## 1. Zweck des Projekts

Quiz Relay ist eine lokale CLI Software, die durch unterschiedliche Auslöser einen Screenshot erstellt, mithilfe eines KI-Dienstes Multiple Choice Aufgaben findet und, das Ergebnis lokal protokolliert und ein kompaktes Lösungsarray per HTTP an einen ESP32 beziehungsweise kompatiblen Mikrocontroller sendet.

Die Software soll modular aufgebaut sein, sodass Auslöser, Screenshot-Erstellung, KI-Anbindung, Ergebnisaufbereitung, Protokollierung und Mikrocontroller-Kommunikation getrennt entwickelt, getestet und ersetzt werden können.

## 2. Zielbild

Die Software stellt eine zentrale Solve-Pipeline bereit:

```text
Trigger → Screenshot → KI-Analyse → strukturierte Lösung → Logging → ESP32-Übertragung
```

Es gibt mindestens zwei Arten, diese Pipeline auszulösen:

1. Ein dauerhaft laufender Prozess lauscht auf ein Mouse-Event.
2. Ein Betriebssystem-Tastaturkürzel, zum Beispiel GNOME Alt+F9, startet einen CLI-Befehl, der dieselbe Pipeline einmalig ausführt.

Beide Auslöser müssen denselben fachlichen Kernprozess verwenden. Es darf keine doppelte Implementierung der Screenshot-, KI-, Logging- oder ESP32-Logik geben.

## 3. Nichtziele

Diese Spezifikation beschreibt nicht:

* eine grafische Benutzeroberfläche,
* eine Webanwendung,
* eine eigenständige ESP32-Firmware,
* die Erstellung oder Verwaltung von Betriebssystem-Tastaturkürzeln innerhalb der Anwendung,
* automatisches Bestehen von Prüfungen oder Umgehung von Prüfungsregeln.

Die Anwendung stellt lediglich technische Funktionen bereit: Bildaufnahme, Bildanalyse, strukturierte Antwortaufbereitung und Weiterleitung an einen Mikrocontroller.

## 4. Begriffe

| Begriff          | Bedeutung                                                                   |
| ---------------- | --------------------------------------------------------------------------- |
| Trigger          | Ereignis, das die Solve-Pipeline startet                                    |
| Shortcut-Trigger | Start durch extern konfiguriertes Betriebssystem-Tastaturkürzel             |
| Mouse-Trigger    | Start durch ein bestimmtes Mouse-Event in einem dauerhaft laufenden Prozess |
| Solve-Pipeline   | Zentraler Ablauf von Screenshot bis ESP32-Übertragung                       |
| Screenshot       | Bild des aktuellen Desktops oder eines definierten Bildschirmbereichs       |
| KI-Antwort       | Rohantwort des KI-Dienstes auf Basis des Screenshots                        |
| Erklärung        | Ausführliche textuelle Begründung der KI                                    |
| Lösungsarray     | Kompakte, maschinenlesbare Antwortstruktur für den ESP32                    |
| Run              | Ein einzelner Pipeline-Durchlauf                                            |
| Audit-Datensatz  | Vollständiger Protokolleintrag eines Runs                                   |

## 5. Funktionaler Umfang

### 5.1 Auslösung per Mouse-Event

Die Software muss einen dauerhaften Prozess bereitstellen, der auf ein konfigurierbares Mouse-Event wartet.

Anforderungen:

* Der Prozess wird über die CLI gestartet.
* Der Prozess läuft dauerhaft, bis er beendet wird.
* Das relevante Mouse-Event ist konfigurierbar.
* Bei Eintreten des Mouse-Events wird genau ein Pipeline-Durchlauf gestartet.
* Während ein Pipeline-Durchlauf aktiv ist, darf ein weiteres Mouse-Event nicht unkontrolliert parallele Läufe erzeugen.
* Das Verhalten bei mehrfachen schnellen Events muss konfigurierbar oder eindeutig definiert sein.

Vorgeschlagenes Standardverhalten:

* Wenn bereits ein Run aktiv ist, werden weitere Mouse-Events ignoriert.
* Optional kann eine Mindestwartezeit zwischen zwei Runs gesetzt werden.

Beispiel:

```bash
quiz-relay listen-mouse
```

Diagnose- und Einrichtungsbefehle:

```bash
quiz-relay listen-mouse --list-events
quiz-relay listen-mouse --scan
quiz-relay listen-mouse --event middle-click
```

Initial zu unterstützende Mouse-Events:

```text
left-click
right-click
middle-click
button4-click
button5-click
scroll-up
scroll-down
scroll-left
scroll-right
```

### 5.2 Auslösung per Betriebssystem-Tastaturkürzel

Die Anwendung selbst muss keinen globalen Hotkey registrieren. Das Betriebssystem, zum Beispiel GNOME, ruft einen CLI-Befehl auf.

Anforderungen:

* Es muss einen CLI-Befehl geben, der genau einen Pipeline-Durchlauf startet.
* Der Befehl muss ohne interaktive Eingabe ausführbar sein.
* Der Befehl muss für GNOME Custom Shortcuts geeignet sein.
* Der Auslöser muss als Quelle im Run-Kontext protokolliert werden.

Beispiel für GNOME:

```bash
quiz-relay solve --source shortcut
```

Beispiel für GNOME-Tastaturkürzel:

```text
Name: Quiz Relay Solve
Command: /home/<user>/.local/bin/quiz-relay solve --source shortcut
Shortcut: Alt+F9
```

### 5.3 Manuelle CLI-Ausführung

Die Software muss über eine CLI bedienbar sein.

Mindestbefehle:

```bash
quiz-relay solve
quiz-relay solve --source shortcut
quiz-relay listen-mouse
quiz-relay test-screenshot
quiz-relay test-esp
quiz-relay config-check
quiz-relay list-monitors
```

Optionale Befehle:

```bash
quiz-relay solve --test-image <file>
quiz-relay parse-response <file>
quiz-relay replay-run <task_id>
quiz-relay doctor
```

#### `quiz-relay solve`

Startet einen vollständigen Pipeline-Durchlauf:

1. Screenshot erstellen.
2. Screenshot optional vorverarbeiten.
3. Screenshot an KI senden.
4. Antwort parsen.
5. Lösung validieren.
6. Run protokollieren.
7. Lösungsarray an ESP32 senden.
8. Ergebnisstatus auf stdout ausgeben.

#### `quiz-relay listen-mouse`

Startet den Mouse-Event-Listener.

#### `quiz-relay test-screenshot`

Erstellt nur einen Screenshot und speichert ihn.

#### `quiz-relay list-monitors`

Listet die vom aktiven Screenshot-Backend erkannten Monitore mit Index, Größe und Position auf.

#### `quiz-relay test-esp`

Sendet ein Testpayload an den ESP32.

#### `quiz-relay config-check`

Prüft, ob die Konfiguration vollständig und plausibel ist.

## 6. Pipeline-Anforderungen

### 6.1 Zentraler Ablauf

Die zentrale Klasse `SolvePipeline` orchestriert den Ablauf.

Pflichtreihenfolge:

```text
RunContext erzeugen
Screenshot erstellen
Screenshot speichern oder referenzieren
KI-Anfrage senden
KI-Rohantwort empfangen
KI-Antwort parsen
Lösung validieren
Audit-Datensatz schreiben
ESP32-Payload bauen
ESP32-Payload senden
Abschlussstatus schreiben
```

Die Pipeline darf keine technischen Details enthalten über:

* konkrete Mouse-Event-Implementierung,
* konkrete GNOME-Integration,
* konkrete Screenshot-Backend-Kommandos,
* konkrete KI-HTTP-Implementierung,
* konkrete Logdateiformate außerhalb definierter Schnittstellen.

Sie ruft nur Schnittstellen auf.

### 6.2 Run-Kontext

Jeder Pipeline-Durchlauf muss einen eindeutigen Kontext besitzen.

Pflichtfelder:

```json
{
  "task_id": "2026-05-07T14-33-21.912Z-8f3a",
  "source": "shortcut",
  "started_at": "2026-05-07T14:33:21.912Z",
  "host": "workstation-01",
  "user": "local-user",
  "config_profile": "default"
}
```

`task_id` muss eindeutig und dateisystemtauglich sein.

Erlaubte Standardwerte für `source`:

* `shortcut`
* `mouse`
* `cli`
* `test`
* `unknown`

## 7. Screenshot-Funktionalität

### 7.1 Anforderungen

Die Anwendung muss einen Screenshot erzeugen können.

Pflichtanforderungen:

* Screenshot des aktuellen Desktops oder konfigurierten Bereichs.
* Ausgabeformat mindestens PNG.
* Speicherung optional konfigurierbar.
* Dateiname muss den Run eindeutig referenzieren.
* Screenshot-Pfad muss im Audit-Datensatz gespeichert werden.

Optionale Anforderungen:

* Auswahl eines bestimmten Monitors.
* Auswahl eines Bildschirmbereichs.
* Verzögerung vor Screenshot-Erstellung.
* Skalierung.
* Kompression.
* Maskierung sensibler Bereiche.

### 7.2 Screenshot-Modul

Vorgeschlagene Klassen:

```text
ScreenshotService
ScreenCaptureBackend
MssScreenshotBackend
GnomeScreenshotBackend
ImagePreprocessor
ScreenshotStore
```

#### `ScreenshotService`

Öffentliche Schnittstelle der Screenshot-Schicht.

Aufgaben:

* Screenshot-Erstellung an Backend delegieren.
* Vorverarbeitung auslösen.
* Speicherung koordinieren.
* Ergebnisobjekt zurückgeben.

#### `ScreenCaptureBackend`

Abstrakte Schnittstelle.

Methoden:

```python
capture(context: RunContext) -> CapturedImage
list_monitors() -> list[MonitorInfo]
```

#### `MssScreenshotBackend`

Initiales Linux-Backend auf Basis der Python-Bibliothek `mss`.

Anforderungen:

* Auswahl eines Monitors per numerischem Index.
* Ausgabe einer Monitorliste für Diagnosezwecke.
* Speicherung als PNG.
* Klare Fehlermeldung, wenn kein kompatibler Desktop-Kontext verfügbar ist.

Hinweis:

* `mss` ist als erster lauffähiger Backend-Kandidat vorgesehen, weil das bestehende Referenzprojekt damit bereits Screenshots, Monitor-Erkennung und PNG-Ausgabe demonstriert.
* Einschränkungen wie X11-Abhängigkeit oder Wayland-Verhalten dürfen nicht in die Pipeline sickern, sondern bleiben Backend-spezifische Fehler.

#### Weitere mögliche Backends

Mögliche spätere technische Implementierungen:

* `gnome-screenshot`
* `grim` auf Wayland/Sway-ähnlichen Umgebungen
* `import` aus ImageMagick auf X11

Die konkrete Wahl ist Implementierungsdetail und muss austauschbar bleiben.

#### `ImagePreprocessor`

Optionale Vorverarbeitung.

Mögliche Aufgaben:

* Bildskalierung,
* Kontrastanpassung,
* Zuschneiden,
* Formatkonvertierung,
* Maskierung.

#### `ScreenshotStore`

Speichert Screenshots.

Pflicht:

* Eindeutiger Dateiname.
* Rückgabe eines stabilen lokalen Pfads.
* Anlage des Zielverzeichnisses, falls es fehlt.

## 8. KI-Funktionalität

### 8.1 Aufgaben der KI-Schicht

Die KI-Schicht muss:

1. den Screenshot entgegennehmen,
2. einen geeigneten Prompt erzeugen,
3. den Screenshot an einen KI-Dienst senden,
4. eine Rohantwort empfangen,
5. diese Rohantwort strukturiert auswerten,
6. eine ausführliche Erklärung und ein kompaktes Lösungsarray bereitstellen.

### 8.2 Antwortformat

Die KI soll strikt JSON zurückgeben.

Pflichtschema:

```json
{
  "explanation": "Ausführliche Begründung der Lösung.",
  "answers": [
    {
      "question": 1,
      "answers": ["A"]
    }
  ],
  "confidence": 0.82
}
```

#### `explanation`

* Menschlich lesbare Erklärung.
* Kann mehrere Sätze enthalten.
* Wird lokal protokolliert.
* Wird standardmäßig nicht an den ESP32 gesendet.

#### `answers`

* Maschinenlesbares Array.
* Wird an den ESP32 gesendet.
* Muss validiert werden.
* Muss auch mehrere Fragen und mehrere richtige Antwortoptionen abbilden können.

#### `confidence`

* Optionaler numerischer Wert zwischen 0 und 1.
* Falls nicht verfügbar, `null`.

### 8.3 Datenmodell `AiSolution`

```python
@dataclass
class AiSolution:
    explanation: str
    answers: list[QuestionAnswer]
    confidence: float | None
    raw_response: str | None
```

```python
@dataclass
class QuestionAnswer:
    question: int
    answers: list[str]
```

Regeln:

* `question` beginnt bei 1.
* `answers` enthält Antwortkennzeichen wie `A`, `B`, `C`, `D`.
* Antwortkennzeichen sollen normalisiert werden, zum Beispiel Großschreibung.
* Leere Antwortlisten sind ungültig, außer ein expliziter Modus erlaubt `unknown`.

### 8.4 Prompt-Anforderung

Der Prompt muss der KI klar vorgeben:

* Suche im Bild nach Multiple-Choice-Aufgaben.
* Löse die Aufgabe fachlich.
* Gib eine ausführliche Erklärung zurück.
* Gib zusätzlich ein kompaktes maschinenlesbares Lösungsarray zurück.
* Antworte strikt als JSON.
* Verwende keine Markdown-Codeblöcke.
* Wenn keine Aufgabe erkannt wird, gib einen definierten Fehlerstatus zurück.
* Erlaube optional eine zusätzliche lokale Prompt-Datei, zum Beispiel `.prompt`, die an die Standardregeln angehängt wird.

Beispiel-Prompt:

```text
Analysiere das bereitgestellte Bild.
Suche darin nach einer oder mehreren Multiple-Choice-Aufgaben.

Gib ausschließlich valides JSON in folgendem Schema zurück:

{
  "explanation": "Ausführliche Begründung der Lösung.",
  "answers": [
    {"question": 1, "answers": ["A"]}
  ],
  "confidence": 0.0
}

Regeln:
- Verwende für Antwortoptionen Großbuchstaben wie A, B, C, D.
- Wenn mehrere Antworten richtig sind, gib mehrere Buchstaben im Array an.
- Wenn mehrere Fragen sichtbar sind, gib für jede Frage ein eigenes Objekt an.
- Wenn keine Multiple-Choice-Aufgabe sichtbar ist, gib answers als leeres Array zurück und erkläre dies in explanation.
- Gib keine Markdown-Codeblöcke zurück.
```

### 8.5 Klassen der KI-Schicht

```text
AiSolverClient
PromptBuilder
AiResponseParser
SolutionValidator
AiProviderConfig
OpenAiVisionProvider
AnthropicVisionProvider
```

#### `AiSolverClient`

Aufgaben:

* API-Anfrage bauen.
* Bild anhängen.
* Timeout anwenden.
* Rohantwort zurückgeben.
* technische Fehler als definierte Anwendungsausnahmen werfen.

#### `PromptBuilder`

Aufgaben:

* Prompt aus Konfiguration und Standardregeln erzeugen.
* Optional Sprache, Detailgrad und Antwortschema konfigurieren.
* Optionale Prompt-Datei laden und an den Standardprompt anhängen.
* Sicherstellen, dass zusätzliche Prompt-Anweisungen das JSON-Ausgabeformat nicht aufheben.

#### `OpenAiVisionProvider` und `AnthropicVisionProvider`

Aufgaben:

* Provider-spezifische Bildanfrage kapseln.
* Provider-native API-Schlüssel aus der Umgebung verwenden.
* Base64- oder Datei-Upload-Details vor `AiSolverClient` verbergen.
* Antworttext in ein gemeinsames Rohantwortmodell überführen.

#### `AiResponseParser`

Aufgaben:

* Rohantwort entgegennehmen.
* JSON extrahieren.
* Felder validieren.
* `AiSolution` erzeugen.
* Parserfehler eindeutig melden.

#### `SolutionValidator`

Aufgaben:

* Antwortschema prüfen.
* Antwortbuchstaben normalisieren.
* leere, doppelte oder ungültige Antworten behandeln.
* Plausibilitätsfehler melden.

## 9. ESP32-Kommunikation

### 9.1 Anforderungen

Die Anwendung muss das Lösungsarray per HTTP an einen ESP32 senden.

Pflicht:

* HTTP POST.
* Konfigurierbare Basis-URL.
* Konfigurierbarer Endpunkt.
* Konfigurierbarer Timeout.
* Kompaktes JSON-Payload.
* Protokollierung von Statuscode und Antworttext.
* Definierter Umgang mit Verbindungsfehlern.

Standardmäßig wird nur das kompakte Lösungsarray gesendet, nicht die ausführliche Erklärung.

### 9.2 Payload an ESP32

Pflichtschema:

```json
{
  "task_id": "2026-05-07T14-33-21.912Z-8f3a",
  "source": "shortcut",
  "answers": [
    {
      "question": 1,
      "answers": ["A"]
    }
  ]
}
```

Optionales erweitertes Schema:

```json
{
  "task_id": "2026-05-07T14-33-21.912Z-8f3a",
  "source": "shortcut",
  "answers": [
    {
      "question": 1,
      "answers": ["A"]
    }
  ],
  "confidence": 0.82,
  "created_at": "2026-05-07T14:33:26.381Z"
}
```

### 9.3 ESP32-Antwort

Die Anwendung erwartet als Erfolg:

* HTTP 2xx.

Optional kann der ESP32 JSON zurückgeben:

```json
{
  "ok": true,
  "received_task_id": "2026-05-07T14-33-21.912Z-8f3a"
}
```

Nicht-2xx-Statuscodes gelten als Übertragungsfehler, müssen aber den lokalen Run nicht ungültig machen. Die KI-Lösung bleibt trotzdem protokolliert.

### 9.4 Klassen der ESP32-Schicht

```text
Esp32Client
Esp32PayloadBuilder
Esp32ResponseValidator
RetryPolicy
```

#### `Esp32Client`

Aufgaben:

* Payload per HTTP senden.
* Timeout anwenden.
* Retry-Strategie nutzen.
* Ergebnisstatus zurückgeben.

#### `Esp32PayloadBuilder`

Aufgaben:

* `AiSolution` und `RunContext` in ESP32-Payload transformieren.
* Keine Erklärung in das Standardpayload aufnehmen.

#### `RetryPolicy`

Standard:

* 2 Wiederholungen.
* Nur bei Verbindungsfehler, Timeout oder 5xx.
* Kein Retry bei 4xx, außer explizit konfiguriert.

## 10. Logging und Audit

### 10.1 Anforderungen

Jeder Run muss nachvollziehbar protokolliert werden.

Mindestens zu speichern:

* `task_id`
* Quelle des Triggers
* Startzeit
* Endzeit
* Dauer
* Screenshot-Pfad
* KI-Rohantwort oder Pfad zur KI-Rohantwort
* geparste Erklärung
* geparstes Lösungsarray
* Validierungsstatus
* ESP32-HTTP-Status
* Fehlerstatus, falls vorhanden

### 10.2 Logdateien

Empfohlene Struktur:

```text
runtime/
  logs/
    app.log
    errors.log
    runs.jsonl
  screenshots/
    2026-05-07T14-33-21.912Z-8f3a.png
  ai_raw/
    2026-05-07T14-33-21.912Z-8f3a.json
```

### 10.3 `runs.jsonl`

Jede Zeile ist ein vollständiger JSON-Datensatz.

Beispiel:

```json
{
  "task_id": "2026-05-07T14-33-21.912Z-8f3a",
  "source": "shortcut",
  "started_at": "2026-05-07T14:33:21.912Z",
  "finished_at": "2026-05-07T14:33:26.381Z",
  "duration_ms": 4469,
  "screenshot_path": "runtime/screenshots/2026-05-07T14-33-21.912Z-8f3a.png",
  "ai_raw_path": "runtime/ai_raw/2026-05-07T14-33-21.912Z-8f3a.json",
  "explanation": "Die richtige Antwort ist A, weil ...",
  "answers": [
    {"question": 1, "answers": ["A"]}
  ],
  "confidence": 0.82,
  "esp32": {
    "sent": true,
    "status_code": 200,
    "response_body": "{\"ok\":true}",
    "duration_ms": 31
  },
  "status": "success"
}
```

### 10.4 Fehlerdatensatz

Auch Fehler müssen als Run protokolliert werden.

Beispiel:

```json
{
  "task_id": "2026-05-07T14-33-21.912Z-8f3a",
  "source": "shortcut",
  "started_at": "2026-05-07T14:33:21.912Z",
  "finished_at": "2026-05-07T14:33:22.104Z",
  "status": "failed",
  "error_stage": "screenshot",
  "error_type": "ScreenshotCaptureError",
  "error_message": "Screenshot backend returned non-zero exit status"
}
```

## 11. Konfiguration

### 11.1 Konfigurationsdatei

Die Anwendung muss über eine Datei konfigurierbar sein.

Empfohlenes Format: TOML.

Beispiel:

```toml
[app]
name = "Quiz Relay"
profile = "default"
runtime_directory = "runtime"
save_screenshots = true
save_ai_raw_response = true
allow_parallel_runs = false
minimum_seconds_between_runs = 1.5

[screenshot]
backend = "mss"
format = "png"
delay_ms = 0
monitor = 1
region = "full"
preprocess = true

[ai]
provider = "openai"
model = "gpt-4.1-mini"
timeout_seconds = 30
response_language = "de"
strict_json = true
prompt_file = ".prompt"
openai_image_detail = "auto"
max_tokens = 1024

[esp32]
enabled = true
base_url = "http://192.168.178.55"
endpoint = "/solution"
timeout_seconds = 2.0
retries = 2
send_explanation = false

[mouse_trigger]
enabled = true
event = "middle-click"
debounce_ms = 750
ignore_while_running = true

[logging]
level = "INFO"
runs_file = "runtime/logs/runs.jsonl"
app_log_file = "runtime/logs/app.log"
error_log_file = "runtime/logs/errors.log"
```

### 11.2 Umgebungsvariablen

Sensible Werte dürfen nicht fest im Repository gespeichert werden.

Beispiele:

```bash
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
QUIZ_RELAY_CONFIG=/path/to/config.toml
QUIZ_RELAY_PROFILE=default
```

Provider-native Secret-Namen wie `OPENAI_API_KEY` und `ANTHROPIC_API_KEY` sollen unterstützt werden, damit Standard-SDKs ohne Sonderlogik funktionieren. App-spezifische Variablen verwenden das Präfix `QUIZ_RELAY_`.

Konfigurationspriorität:

1. CLI-Argumente
2. Umgebungsvariablen
3. Konfigurationsdatei
4. Standardwerte

## 12. Fehlerbehandlung

### 12.1 Fehlerklassen

Vorgeschlagene zentrale Fehlerklassen:

```text
QuizRelayError
ConfigurationError
TriggerError
ScreenshotCaptureError
ImagePreprocessingError
AiRequestError
AiTimeoutError
AiResponseParseError
SolutionValidationError
Esp32ConnectionError
Esp32HttpError
AuditWriteError
```

### 12.2 Fehlerstufen

Jeder Fehler muss einer Stufe zugeordnet werden:

```text
configuration
trigger
screenshot
preprocess
ai_request
ai_parse
solution_validation
esp32_send
audit
unknown
```

### 12.3 Verhalten bei Fehlern

| Fehler                       | Verhalten                                                              |
| ---------------------------- | ---------------------------------------------------------------------- |
| Konfiguration ungültig       | Programmstart abbrechen                                                |
| Screenshot fehlgeschlagen    | Run als fehlgeschlagen protokollieren, kein KI-Aufruf                  |
| KI nicht erreichbar          | Run als fehlgeschlagen protokollieren, kein ESP32-Versand              |
| KI-Antwort nicht parsebar    | Rohantwort speichern, Run als fehlgeschlagen protokollieren            |
| Lösung ungültig              | Kein ESP32-Versand, Run als fehlgeschlagen protokollieren              |
| ESP32 nicht erreichbar       | Run mit KI-Lösung speichern, ESP32-Status als fehlgeschlagen markieren |
| Audit-Logging fehlgeschlagen | Fehler auf stderr und app.log schreiben                                |

## 13. Nebenläufigkeit und Sperren

### 13.1 Standardverhalten

Standardmäßig darf nur ein Pipeline-Durchlauf gleichzeitig aktiv sein.

Grund:

* Screenshots könnten sich überlappen.
* KI-Anfragen sind teuer und langsam.
* Mehrere ESP32-Payloads könnten Reihenfolgeprobleme erzeugen.

### 13.2 Locking

Die Anwendung soll einen Prozess- oder Dateilock verwenden.

Beispiel:

```text
runtime/quiz-relay.lock
```

Verhalten:

* Wenn ein Run aktiv ist und ein neuer Trigger kommt, wird der neue Trigger ignoriert oder mit definierter Meldung beendet.
* Das Verhalten wird über `allow_parallel_runs` gesteuert.

## 14. Sicherheits- und Datenschutzanforderungen

### 14.1 Screenshot-Sensibilität

Screenshots können private oder vertrauliche Informationen enthalten.

Anforderungen:

* Der Speicherort muss konfigurierbar sein.
* Screenshot-Speicherung muss deaktivierbar sein.
* Rohantwort-Speicherung muss deaktivierbar sein.
* Logs dürfen keine API-Schlüssel enthalten.
* Konfiguration darf keine Klartextgeheimnisse erfordern.

### 14.2 Netzwerk

Anforderungen:

* KI-Kommunikation nutzt HTTPS, sofern externer Dienst.
* ESP32-Kommunikation kann lokal HTTP verwenden.
* Timeouts sind Pflicht.
* Keine unendlichen Wiederholungen.

### 14.3 Datenminimierung ESP32

Standardmäßig wird an den ESP32 nur gesendet:

* `task_id`
* `source`
* `answers`
* optional `confidence`

Nicht standardmäßig gesendet werden:

* Screenshot,
* Erklärung,
* KI-Rohantwort,
* lokale Pfade,
* Benutzername,
* Hostname.

## 15. Modul- und Dateistruktur

Empfohlene Projektstruktur:

```text
quiz-relay/
  pyproject.toml
  README.md
  config.example.toml
  .env.example

  src/
    quiz_relay/
      __init__.py
      app.py
      cli.py
      config.py
      errors.py

      pipeline/
        __init__.py
        solve_pipeline.py
        run_context.py
        result_models.py
        locking.py

      triggers/
        __init__.py
        mouse_listener.py
        shortcut_entrypoint.py

      screenshot/
        __init__.py
        screenshot_service.py
        backends.py
        monitor_models.py
        image_preprocessor.py
        screenshot_store.py

      ai/
        __init__.py
        ai_solver_client.py
        providers.py
        prompt_builder.py
        response_parser.py
        solution_validator.py
        provider_config.py

      esp32/
        __init__.py
        esp32_client.py
        payload_builder.py
        response_validator.py
        retry_policy.py

      audit/
        __init__.py
        run_logger.py
        audit_store.py
        log_setup.py

  tests/
    test_config.py
    test_run_context.py
    test_solve_pipeline.py
    test_response_parser.py
    test_solution_validator.py
    test_payload_builder.py
    test_esp32_client.py
    test_screenshot_service.py
    test_mouse_listener.py
    test_monitor_listing.py

  docs/
    gnome_shortcut.md
    esp32_protocol.md
```

Initiale Python-Abhängigkeiten:

```text
mss
openai
anthropic
pynput
python-dotenv
httpx oder requests
```

Die Referenz `examfit/` nutzt diese Pakete bereits für Screenshot, KI-Anbindung und Mouse-Events. Quiz Relay soll sie jedoch über die oben genannten Module kapseln.

Der CLI-Entry-Point muss in `pyproject.toml` den ausführbaren Namen `quiz-relay` bereitstellen:

```toml
[project.scripts]
quiz-relay = "quiz_relay.cli:main"
```

## 16. Klassenübersicht

### 16.1 `SolvePipeline`

Zweck: Orchestriert den vollständigen Ablauf.

Methoden:

```python
run(source: str = "cli") -> PipelineResult
```

Abhängigkeiten:

* `ScreenshotService`
* `AiSolverClient`
* `AiResponseParser`
* `SolutionValidator`
* `Esp32Client`
* `RunLogger`
* `PipelineLock`

Darf nicht enthalten:

* OS-spezifischen Screenshot-Code,
* konkrete Mouse-Event-Abfragen,
* harte URLs,
* API-Schlüssel,
* direkte Dateipfade ohne Konfiguration.

### 16.2 `RunContext`

Zweck: Hält Metadaten eines Runs.

Felder:

```python
task_id: str
source: str
started_at: datetime
host: str | None
user: str | None
config_profile: str
```

### 16.3 `PipelineResult`

Zweck: Rückgabeobjekt der Pipeline.

Felder:

```python
context: RunContext
status: Literal["success", "failed", "partial"]
screenshot_path: str | None
solution: AiSolution | None
esp32_result: Esp32SendResult | None
error: ErrorInfo | None
```

### 16.4 `MouseEventListener`

Zweck: Wartet auf konfiguriertes Mouse-Event.

Methoden:

```python
start() -> None
stop() -> None
```

### 16.5 `ShortcutEntryPoint`

Zweck: Dünne Hülle für einmalige Ausführung über CLI/Shortcut.

Methoden:

```python
run_once() -> PipelineResult
```

### 16.6 `ScreenshotService`

Zweck: Erstellt, verarbeitet und speichert Screenshots.

Methoden:

```python
capture(context: RunContext) -> ScreenshotResult
list_monitors() -> list[MonitorInfo]
```

### 16.7 `AiSolverClient`

Zweck: Sendet Bild und Prompt an KI-Dienst.

Methoden:

```python
solve_image(image: ScreenshotResult, context: RunContext) -> AiRawResponse
```

### 16.8 `AiResponseParser`

Zweck: Wandelt Rohantwort in `AiSolution`.

Methoden:

```python
parse(raw: AiRawResponse) -> AiSolution
```

### 16.9 `SolutionValidator`

Zweck: Prüft und normalisiert Lösungen.

Methoden:

```python
validate(solution: AiSolution) -> AiSolution
```

### 16.10 `Esp32Client`

Zweck: Sendet kompaktes Ergebnis an ESP32.

Methoden:

```python
send_solution(context: RunContext, solution: AiSolution) -> Esp32SendResult
```

### 16.11 `RunLogger`

Zweck: Schreibt strukturierte Logs.

Methoden:

```python
write_success(result: PipelineResult) -> None
write_failure(result: PipelineResult) -> None
write_partial(result: PipelineResult) -> None
```

## 17. Datenmodelle

### 17.1 `QuestionAnswer`

```python
@dataclass
class QuestionAnswer:
    question: int
    answers: list[str]
```

Validierungsregeln:

* `question >= 1`
* `answers` ist nicht leer
* Werte in `answers` sind Großbuchstaben
* Doppelte Antwortbuchstaben werden entfernt

### 17.2 `AiSolution`

```python
@dataclass
class AiSolution:
    explanation: str
    answers: list[QuestionAnswer]
    confidence: float | None = None
    raw_response: str | None = None
```

Validierungsregeln:

* `explanation` darf leer sein, sollte aber protokolliert werden.
* `answers` darf nur leer sein, wenn keine Aufgabe erkannt wurde.
* `confidence`, falls vorhanden, liegt zwischen 0 und 1.

### 17.3 `Esp32SendResult`

```python
@dataclass
class Esp32SendResult:
    sent: bool
    status_code: int | None
    response_body: str | None
    duration_ms: int
    error: str | None = None
```

### 17.4 `ScreenshotResult`

```python
@dataclass
class ScreenshotResult:
    path: str
    mime_type: str
    width: int | None
    height: int | None
    size_bytes: int | None
```

### 17.5 `MonitorInfo`

```python
@dataclass
class MonitorInfo:
    index: int
    left: int
    top: int
    width: int
    height: int
```

`index` ist der vom aktiven Screenshot-Backend verwendete Monitor-Index und muss in CLI-Ausgaben sowie Konfiguration konsistent verwendet werden.

## 18. CLI-Spezifikation

### 18.1 Allgemeine Optionen

```bash
quiz-relay [COMMAND] [OPTIONS]
```

Globale Optionen:

```text
--config <path>       Pfad zur Konfiguration
--profile <name>      Konfigurationsprofil
--verbose             Ausführlichere Logs
--quiet               Nur Fehler ausgeben
```

### 18.2 `solve`

```bash
quiz-relay solve [--source SOURCE] [--no-esp32] [--save-screenshot true|false] [--test-image <path>]
```

`--test-image` verwendet eine vorhandene PNG- oder JPEG-Datei als Eingabe für KI, Parser, Validator, Logging und optional ESP32-Versand. Es wird dabei kein neuer Screenshot erstellt.

Erwartetes stdout bei Erfolg:

```json
{
  "status": "success",
  "task_id": "2026-05-07T14-33-21.912Z-8f3a",
  "answers": [
    {"question": 1, "answers": ["A"]}
  ],
  "esp32_sent": true
}
```

Exit-Codes:

| Code | Bedeutung                 |
| ---: | ------------------------- |
|    0 | Erfolg                    |
|    1 | Allgemeiner Fehler        |
|    2 | Konfigurationsfehler      |
|    3 | Screenshot-Fehler         |
|    4 | KI-Fehler                 |
|    5 | Parse-/Validierungsfehler |
|    6 | ESP32-Fehler              |
|    7 | Run bereits aktiv         |

Wenn die KI-Lösung erfolgreich war, aber der ESP32 nicht erreichbar ist, ist der empfohlene Exit-Code `6`, während der Run im Audit als `partial` gespeichert wird.

### 18.3 `listen-mouse`

```bash
quiz-relay listen-mouse [--event EVENT] [--scan] [--list-events]
```

Verhalten:

* Startet Listener.
* Schreibt Status in `app.log`.
* Beendet sauber bei SIGINT/SIGTERM.
* `--list-events` gibt die unterstützten Mouse-Events aus und beendet sich.
* `--scan` gibt erkannte Mouse-Events aus und startet keine Pipeline.
* `--event` überschreibt das konfigurierte Mouse-Event.

### 18.4 `test-screenshot`

```bash
quiz-relay test-screenshot
```

Erzeugt Screenshot, speichert ihn und gibt Pfad aus.

### 18.5 `list-monitors`

```bash
quiz-relay list-monitors
```

Gibt die vom Screenshot-Backend erkannten Monitore aus.

### 18.6 `test-esp`

```bash
quiz-relay test-esp
```

Sendet Beispielpayload:

```json
{
  "task_id": "test",
  "source": "test",
  "answers": [
    {"question": 1, "answers": ["A"]}
  ]
}
```

## 19. Abnahmekriterien

### 19.1 Pipeline

* Ein Aufruf von `quiz-relay solve` führt genau einen vollständigen Run aus.
* Mouse-Trigger und Shortcut-Trigger verwenden dieselbe `SolvePipeline`.
* Bei erfolgreicher KI-Antwort wird ein valides Lösungsarray erzeugt.
* Das Lösungsarray wird per HTTP POST an den ESP32 gesendet.
* Der Run wird vollständig in `runs.jsonl` protokolliert.

### 19.2 Screenshot

* `quiz-relay test-screenshot` erzeugt eine PNG-Datei.
* `quiz-relay list-monitors` gibt mindestens Index, Größe und Position der erkannten Monitore aus.
* Der Screenshot-Pfad erscheint im Audit-Datensatz.
* Screenshot-Speicherung kann deaktiviert werden.

### 19.3 KI-Antwort

* Valides JSON wird korrekt geparst.
* `quiz-relay solve --test-image <file>` durchläuft KI, Parser, Validator und Logging ohne neuen Screenshot.
* Markdown-Codeblöcke in der KI-Antwort werden toleriert, falls der Parser dies vorsieht.
* Ungültiges JSON erzeugt einen definierten Parse-Fehler.
* Ungültige Antwortbuchstaben erzeugen einen definierten Validierungsfehler oder werden nach Regel normalisiert.

### 19.4 ESP32

* Der HTTP-Endpunkt ist konfigurierbar.
* Bei 2xx gilt die Übertragung als erfolgreich.
* Bei Timeout wird nach Konfiguration wiederholt.
* Bei endgültigem Fehler bleibt die KI-Lösung lokal erhalten.

### 19.5 Logging

* Jeder Run hat eine eindeutige `task_id`.
* Erfolgreiche, fehlgeschlagene und teilweise erfolgreiche Runs werden protokolliert.
* API-Schlüssel erscheinen nicht in Logs.

### 19.6 Nebenläufigkeit

* Bei `allow_parallel_runs = false` kann nicht mehr als ein Run gleichzeitig laufen.
* Ein zweiter Trigger während eines aktiven Runs wird ignoriert oder mit Exit-Code `7` beendet.
* `quiz-relay listen-mouse --scan` startet keine Pipeline und eignet sich zur Ermittlung des Mouse-Event-Namens.

## 20. Teststrategie

### 20.1 Unit-Tests

Pflichttests:

```text
test_response_parser.py
test_solution_validator.py
test_payload_builder.py
test_run_context.py
test_config.py
```

#### Parser-Tests

Fälle:

* Valides JSON.
* JSON mit mehreren Fragen.
* Mehrere richtige Antworten.
* Kleinbuchstaben werden normalisiert.
* Markdown-Codeblock um JSON.
* Kein JSON vorhanden.
* Fehlendes Feld `answers`.
* `confidence` außerhalb 0 bis 1.

#### Payload-Tests

Fälle:

* Erklärung wird standardmäßig nicht gesendet.
* `task_id` wird übernommen.
* Antwortarray wird korrekt serialisiert.
* Leeres Antwortarray wird gemäß Regel behandelt.

#### Konfigurations-Tests

Fälle:

* Provider-native Secrets werden nicht in Konfigurationsdateien verlangt.
* `OPENAI_API_KEY` und `ANTHROPIC_API_KEY` werden als Secret-Quellen unterstützt.
* `prompt_file` wird optional geladen.
* Ungültige Monitor-Indizes werden verständlich gemeldet.

### 20.2 Integrationstests

Pflicht:

* Pipeline mit gemocktem Screenshot-Service.
* Pipeline mit gemocktem KI-Client.
* Pipeline mit `--test-image`, ohne Screenshot-Backend-Aufruf.
* Pipeline mit lokalem HTTP-Testserver für ESP32.
* Monitorliste mit gemocktem Screenshot-Backend.
* Fehlerfall KI-Timeout.
* Fehlerfall ESP32-Timeout.

### 20.3 Manuelle Tests

Pflicht:

1. GNOME Shortcut Alt+F9 auslösen.
2. Prüfen, ob Screenshot entsteht.
3. Prüfen, ob KI-Antwort gespeichert wird.
4. Prüfen, ob `runs.jsonl` Eintrag enthält.
5. Prüfen, ob ESP32 Payload empfängt.
6. Mouse-Listener starten und Trigger auslösen.
7. `quiz-relay list-monitors` ausführen und Monitor-Index für die Konfiguration übernehmen.
8. `quiz-relay listen-mouse --scan` ausführen und den gewünschten Eventnamen prüfen.

## 21. Qualitätseigenschaften

### 21.1 Wartbarkeit

* Fachlogik liegt in der Pipeline.
* Trigger sind dünn.
* Externe Dienste sind über Schnittstellen gekapselt.
* Parser und Payload-Builder sind separat testbar.

### 21.2 Robustheit

* Timeouts für alle Netzwerkoperationen.
* Definierte Fehlerklassen.
* Keine unendlichen Retry-Schleifen.
* Lock gegen parallele Runs.

### 21.3 Austauschbarkeit

Austauschbar sein müssen:

* Screenshot-Backend,
* KI-Anbieter,
* Prompt,
* ESP32-Endpunkt,
* Mouse-Event-Quelle.

### 21.4 Beobachtbarkeit

* Strukturierte Run-Logs.
* Technische App-Logs.
* Fehlerlogs.
* Eindeutige `task_id` über alle Artefakte.

## 22. Minimal lauffähige Version

Für eine erste Neuimplementierung reicht folgender Umfang:

```text
CLI solve
CLI test-screenshot
CLI test-esp
CLI list-monitors
ScreenshotService mit einem Backend
MssScreenshotBackend
AiSolverClient mit einem Anbieter
PromptBuilder
AiResponseParser
SolutionValidator
Esp32Client
RunLogger
SolvePipeline
```

Danach:

```text
MouseEventListener
Mouse-Event-Scan und Eventliste
GNOME Shortcut-Dokumentation
Locking
RetryPolicy
AuditStore
Doctor-Befehl
```

## 23. Empfohlene Implementierungsreihenfolge

1. Datenmodelle definieren.
2. Konfiguration laden und validieren.
3. Parser und Validator implementieren.
4. ESP32-Payload-Builder implementieren.
5. ESP32-Testclient implementieren.
6. Screenshot-Service mit `mss`-Backend und Monitorliste implementieren.
7. KI-Client mit OpenAI-Provider implementieren.
8. Optional Anthropic-Provider ergänzen.
9. Solve-Pipeline zusammensetzen.
10. CLI `solve`, `test-screenshot`, `list-monitors` und `test-esp` implementieren.
11. `--test-image` für KI-/Parser-Diagnose implementieren.
12. Audit-Logging implementieren.
13. Mouse-Listener mit Eventliste und Scan-Modus implementieren.
14. GNOME-Shortcut dokumentieren.
15. Sperrmechanismus ergänzen.
16. Integrationstests schreiben.

## 24. Beispiel: Pipeline-Pseudocode

```python
class SolvePipeline:
    def __init__(
        self,
        screenshot_service,
        ai_solver_client,
        response_parser,
        solution_validator,
        esp32_client,
        run_logger,
        lock,
    ):
        self.screenshot_service = screenshot_service
        self.ai_solver_client = ai_solver_client
        self.response_parser = response_parser
        self.solution_validator = solution_validator
        self.esp32_client = esp32_client
        self.run_logger = run_logger
        self.lock = lock

    def run(self, source: str) -> PipelineResult:
        context = RunContext.create(source=source)

        if not self.lock.acquire(context):
            return PipelineResult.locked(context)

        try:
            screenshot = self.screenshot_service.capture(context)
            raw_response = self.ai_solver_client.solve_image(screenshot, context)
            solution = self.response_parser.parse(raw_response)
            solution = self.solution_validator.validate(solution)

            esp32_result = self.esp32_client.send_solution(context, solution)

            if esp32_result.sent:
                result = PipelineResult.success(
                    context=context,
                    screenshot=screenshot,
                    solution=solution,
                    esp32_result=esp32_result,
                )
            else:
                result = PipelineResult.partial(
                    context=context,
                    screenshot=screenshot,
                    solution=solution,
                    esp32_result=esp32_result,
                )

            self.run_logger.write(result)
            return result

        except QuizRelayError as exc:
            result = PipelineResult.failed(context=context, error=exc)
            self.run_logger.write(result)
            return result

        finally:
            self.lock.release(context)
```

## 25. Beispiel: ESP32-Payload-Builder

```python
class Esp32PayloadBuilder:
    def build(self, context: RunContext, solution: AiSolution) -> dict:
        return {
            "task_id": context.task_id,
            "source": context.source,
            "answers": [
                {
                    "question": item.question,
                    "answers": item.answers,
                }
                for item in solution.answers
            ],
        }
```

## 26. Beispiel: Parser-Verhalten

Eingabe:

```json
{
  "explanation": "Frage 1 ist A, weil ...",
  "answers": [
    {"question": 1, "answers": ["a"]}
  ],
  "confidence": 0.91
}
```

Ausgabe nach Parser und Validator:

```json
{
  "explanation": "Frage 1 ist A, weil ...",
  "answers": [
    {"question": 1, "answers": ["A"]}
  ],
  "confidence": 0.91
}
```

## 27. Dokumentation

Das Projekt soll mindestens folgende Dokumentation enthalten:

```text
README.md
config.example.toml
docs/gnome_shortcut.md
docs/esp32_protocol.md
docs/development.md
```

### README-Inhalte

* Zweck des Projekts.
* Installation.
* Konfiguration.
* CLI-Beispiele.
* GNOME-Shortcut-Hinweis.
* ESP32-Payload-Format.
* Sicherheits- und Datenschutzhinweise.

### `docs/gnome_shortcut.md`

Muss beschreiben:

* GNOME Settings öffnen.
* Keyboard Shortcuts öffnen.
* Custom Shortcut anlegen.
* Befehl `quiz-relay solve --source shortcut` eintragen.
* Alt+F9 zuweisen.
* Testdurchlauf ausführen.

### `docs/esp32_protocol.md`

Muss beschreiben:

* HTTP-Methode.
* Endpunkt.
* JSON-Schema.
* Beispielpayload.
* Erwartete Antwort.
* Fehlerfälle.

## 28. Offene Designentscheidungen

Diese Punkte müssen vor oder während der Implementierung entschieden werden:

1. Wird immer der gesamte Desktop aufgenommen oder nur ein Bereich?
2. Soll die Screenshot-Speicherung standardmäßig aktiv sein?
3. Soll initial ausschließlich OpenAI unterstützt werden oder direkt zusätzlich Anthropic?
4. Soll die KI-Erklärung immer gespeichert werden?
5. Soll bei leerem `answers`-Array trotzdem ein Payload an den ESP32 gesendet werden?
6. Soll `middle-click` als Default-Mouse-Event beibehalten werden?
7. Soll der Mouse-Listener als systemd-user-service laufen?
8. Soll es mehrere Konfigurationsprofile geben?
9. Wie lange sollen Screenshots und Rohantworten aufbewahrt werden?
10. Welche Wayland/GNOME-Alternative wird ergänzt, falls `mss` auf dem Zielsystem nicht funktioniert?

## 29. Prüfmatrix für bestehendes Projekt

Diese Matrix kann genutzt werden, um ein bestehendes Projekt gegen die Zielarchitektur zu prüfen.

| Prüffrage                                                      | Erwartung                          |
| -------------------------------------------------------------- | ---------------------------------- |
| Gibt es eine zentrale Pipeline?                                | Ja, Trigger delegieren nur dorthin |
| Sind Mouse- und Shortcut-Auslösung getrennt von der Fachlogik? | Ja                                 |
| Ist Screenshot-Erstellung separat gekapselt?                   | Ja                                 |
| Ist KI-Kommunikation separat gekapselt?                        | Ja                                 |
| Gibt es einen Parser für strukturierte KI-Antworten?           | Ja                                 |
| Wird das Lösungsarray validiert?                               | Ja                                 |
| Wird nur das kompakte Ergebnis an den ESP32 gesendet?          | Ja                                 |
| Sind Timeouts konfigurierbar?                                  | Ja                                 |
| Sind Logs strukturiert?                                        | Ja, mindestens JSONL für Runs      |
| Gibt es definierte Fehlerklassen?                              | Ja                                 |
| Gibt es Tests für Parser und Payload-Builder?                  | Ja                                 |
| Werden API-Schlüssel aus Logs herausgehalten?                  | Ja                                 |
| Sind parallele Runs geregelt?                                  | Ja                                 |

## 30. Zusammenfassung

Quiz Relay soll als modularer, testbarer Pipeline-Dienst umgesetzt werden. Die entscheidende Architekturregel lautet:

```text
Alle Auslöser starten denselben Solve-Prozess.
```

Mouse-Listener, GNOME-Tastaturkürzel und CLI dürfen keine eigene fachliche Logik enthalten. Sie liefern nur den Startimpuls und eine Quellenkennung.

Die fachliche Verantwortung liegt in `SolvePipeline`. Alle externen Abhängigkeiten — Screenshot-System, KI-Dienst, Dateisystem und ESP32 — werden über klar getrennte Komponenten angebunden. Dadurch bleibt das Projekt testbar, erweiterbar und robust gegenüber Änderungen der Umgebung.
