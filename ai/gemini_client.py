# codeeditor/ai/gemini_client.py
# Gemini API wrapper using the google-genai SDK.

from __future__ import annotations

from codeeditor.ai.worker import AIWorker
from codeeditor.config import DEFAULT_GEMINI_MODEL


class GeminiClient:
    """Async-friendly wrapper around the Gemini API."""

    def __init__(self, api_key: str, model_name: str = DEFAULT_GEMINI_MODEL):
        self._api_key = api_key
        self._model_name = model_name

    def send(
        self,
        prompt: str,
        code_context: str = "",
        attachments: list[dict] | None = None,
        history: list[dict] | None = None,
    ) -> AIWorker:
        """Build request and return a started AIWorker thread."""
        contents = self._build_request(prompt, code_context, attachments, history)
        api_key = self._api_key
        model_name = self._model_name

        def _call() -> str:
            from google import genai

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
            )
            return response.text

        worker = AIWorker(_call)
        worker.start()
        return worker

    def _build_request(
        self,
        prompt: str,
        code_context: str,
        attachments: list[dict] | None,
        history: list[dict] | None,
    ) -> list[dict] | str:
        """Assemble contents for the Gemini API.

        With history, returns a list of turn dicts for multi-turn conversation.
        Without history, returns a plain string (single-turn, original behaviour).
        """
        user_parts: list[str] = []

        if code_context:
            user_parts.append(f"Here is the code I'm working with:\n```\n{code_context}\n```")

        if attachments:
            for att in attachments:
                user_parts.append(
                    f"Attached file '{att['filename']}' ({att['mime_type']}):\n"
                    f"```\n{att['content']}\n```"
                )

        user_parts.append(prompt)
        current_text = "\n\n".join(user_parts)

        if not history:
            return current_text

        contents: list[dict] = []
        for turn in history:
            role = "model" if turn["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": turn["content"]}]})
        contents.append({"role": "user", "parts": [{"text": current_text}]})
        return contents
