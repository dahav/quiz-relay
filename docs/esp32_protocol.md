# ESP32 Protocol

Quiz Relay sends a compact JSON payload via HTTP POST to the configured endpoint.

```json
{
  "task_id": "2026-05-07T14-33-21.912Z-8f3a",
  "source": "shortcut",
  "answers": [
    {"question": 1, "answers": ["A"]}
  ],
  "confidence": 0.82,
  "created_at": "2026-05-07T14:33:26.381Z"
}
```

HTTP 2xx is treated as success. Timeouts and 5xx responses can be retried depending on configuration.
