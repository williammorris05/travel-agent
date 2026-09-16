"""Stateless Gemini Interactions REST adapter, with bounded local usage."""

from threading import Lock

import httpx

from travel_agent.providers.openai_transport import ModelUnavailable
from travel_agent.settings import Settings


class GeminiTransport:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client
        self.calls = 0
        self.lock = Lock()

    async def complete_json(self, prompt: str, schema: dict) -> str:
        with self.lock:
            if not self.settings.chat_available or self.calls >= self.settings.model_max_calls:
                raise ModelUnavailable("Model unavailable or local call allowance exhausted")
            self.calls += 1
        payload = {"model": self.settings.model_name, "input": prompt, "store": False,
                   "system_instruction": "Extract travel preferences using the supplied rules and schema. No tools or free-form claims.",
                   "response_format": {"type": "text", "mime_type": "application/json", "schema": schema},
                   "generation_config": {"max_output_tokens": 1600}}
        url = "https://generativelanguage.googleapis.com/v1beta/interactions"
        headers = {"x-goog-api-key": self.settings.gemini_api_key.get_secret_value()}
        try:
            if self.client is not None:
                response = await self.client.post(url, json=payload, headers=headers, timeout=25)
            else:
                async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
                    response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()
            if body.get("status") != "completed":
                raise ValueError("Incomplete response")
            texts = [part["text"] for step in body.get("steps", []) if step.get("type") == "model_output"
                     for part in step.get("content", []) if part.get("type") == "text"]
            if len(texts) != 1:
                raise ValueError("Missing structured response")
            return texts[0]
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError) as exc:
            raise ModelUnavailable("Gemini could not complete the message. No trip changes were saved.") from exc
