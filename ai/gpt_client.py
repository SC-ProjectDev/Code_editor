# codeeditor/ai/gpt_client.py
# GPT API wrapper using openai.

from __future__ import annotations

from codeeditor.ai.worker import AIWorker
from codeeditor.config import DEFAULT_GPT_MODEL


class GPTClient:
    """Async-friendly wrapper around the OpenAI GPT API."""

    def __init__(self, api_key: str, model_name: str = DEFAULT_GPT_MODEL):
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
        messages = self._build_messages(prompt, code_context, attachments, history)
        api_key = self._api_key
        model_name = self._model_name

        def _call() -> str:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
            )
            return response.choices[0].message.content

        worker = AIWorker(_call)
        worker.start()
        return worker

    def _build_messages(
        self,
        prompt: str,
        code_context: str,
        attachments: list[dict] | None,
        history: list[dict] | None,
    ) -> list[dict]:
        """Build the OpenAI messages array, prepending prior conversation history."""
        messages: list[dict] = [
            {
                "role": "system",
                "content": "You are a helpful coding assistant. Respond with clear, concise answers. Use code blocks for code.",
            }
        ]

        for turn in (history or []):
            messages.append({"role": turn["role"], "content": turn["content"]})

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

        messages.append({"role": "user", "content": "\n\n".join(user_parts)})
        return messages
