# HTTP Relay

Quiz Relay can send the validated AI result to a configured HTTP endpoint after a run.

Use JSON mode to send a POST request:

```toml
[http_relay]
enabled = true
url = "http://127.0.0.1:8080/solution"
mode = "json"
```

Example JSON body:

```json
{
  "task_id": "2026-05-07T16-33-21.912+0200-8f3a",
  "source": "shortcut",
  "answers": [
    {"question": 1, "answers": ["A"]}
  ],
  "confidence": 0.82,
  "created_at": "2026-05-07T16:33:26.381+02:00"
}
```

Use query mode to send a GET request with mapped values as query parameters:

```toml
[http_relay]
enabled = true
url = "http://127.0.0.1:8080/solution"
mode = "query"
```

The `[http_relay.fields]` table maps outgoing field names to source expressions:

```toml
[http_relay.fields]
id = "context.task_id"
answer = "solution.answers_text"
confidence = "solution.confidence"
reason = "solution.explanation"
```

Supported expressions:

- `context.task_id`
- `context.source`
- `context.started_at`
- `context.config_profile`
- `context.host`
- `context.user`
- `solution.answers`
- `solution.answer_letters`
- `solution.answers_text`
- `solution.explanation`
- `solution.confidence`
- `solution.raw_response`
- `meta.created_at`
- `literal:<value>`

HTTP 2xx is treated as success. HTTP 4xx is returned immediately. Timeouts and HTTP 5xx responses are retried according to `retries`.
