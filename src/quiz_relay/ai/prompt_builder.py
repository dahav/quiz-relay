from __future__ import annotations

from pathlib import Path

from quiz_relay.config import AiConfig


class PromptBuilder:
    def __init__(self, config: AiConfig, base_dir: Path = Path(".")) -> None:
        self.config = config
        self.base_dir = base_dir

    def build(self) -> str:
        prompt = f"""Analysiere das bereitgestellte Bild.
Suche darin nach einer oder mehreren Multiple-Choice-Aufgaben.

Gib ausschliesslich valides JSON in folgendem Schema zurueck:

{{
  "explanation": "Ausfuehrliche Begruendung der Loesung.",
  "answers": [
    {{"question": 1, "answers": ["A"]}}
  ],
  "confidence": 0.0
}}

Regeln:
- Antworte auf {self.config.response_language}.
- Verwende fuer Antwortoptionen Grossbuchstaben wie A, B, C, D.
- Wenn mehrere Antworten richtig sind, gib mehrere Buchstaben im Array an.
- Wenn mehrere Fragen sichtbar sind, gib fuer jede Frage ein eigenes Objekt an.
- Wenn keine Multiple-Choice-Aufgabe sichtbar ist, gib answers als leeres Array zurueck und erklaere dies in explanation.
- Gib keine Markdown-Codebloecke zurueck.
"""
        extra = self._read_prompt_file()
        if extra:
            prompt = f"{prompt}\nZusaetzliche Anweisungen:\n{extra}\n"
        return prompt

    def _read_prompt_file(self) -> str:
        if self.config.prompt_file is None:
            return ""
        prompt_path = self.config.prompt_file
        if not prompt_path.is_absolute():
            prompt_path = self.base_dir / prompt_path
        if not prompt_path.is_file():
            return ""
        return prompt_path.read_text(encoding="utf-8").strip()
