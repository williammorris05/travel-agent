"""Bounded Responses API transport. No automatic retry or tool invocation."""

from threading import Lock

import httpx

from travel_agent.settings import Settings


class ModelUnavailable(Exception):
    pass


class OpenAITransport:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None, *, ledger=None):
        self.ledger = ledger
        self.settings = settings
        self.client = client
        self.calls = 0
        self.lock = Lock()

    async def complete_json(self, prompt: str, schema: dict) -> str:
        with self.lock:
            if not self.settings.chat_available or self.calls >= self.settings.model_max_calls:
                raise ModelUnavailable("Model is not configured or the local call allowance is exhausted.")
            if self.ledger is not None and not self.ledger.reserve('model', self.settings.model_max_calls):
                raise ModelUnavailable("Persistent model allowance unavailable or exhausted.")
            self.calls += 1
        payload = {
            "model": self.settings.model_name, "store": False,
            "instructions": "Interpret the travel input according to the supplied rules. Return only the structured extraction. Do not invoke tools.",
            "input": prompt, "max_output_tokens": 1600,
            "text": {"format": {"type": "json_schema", "name": "trip_interpretation", "strict": True, "schema": schema}},
        }
        try:
            if self.client is not None:
                response = await self.client.post("https://api.openai.com/v1/responses", json=payload,
                    headers={"Authorization": f"Bearer {self.settings.openai_api_key.get_secret_value()}"}, timeout=25)
            else:
                async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
                    response = await client.post("https://api.openai.com/v1/responses", json=payload,
                        headers={"Authorization": f"Bearer {self.settings.openai_api_key.get_secret_value()}"})
            response.raise_for_status()
            body = response.json()
            if body.get("status") != "completed":
                raise ValueError("Incomplete model response")
            content = [part for item in body.get("output", []) if item.get("type") == "message" for part in item.get("content", [])]
            if any(part.get("type") == "refusal" for part in content):
                raise ValueError("Model refused extraction")
            texts = [part["text"] for part in content if part.get("type") == "output_text"]
            if len(texts) != 1:
                raise ValueError("Missing structured output")
            return texts[0]
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as exc:
            # Never expose provider bodies, credentials, or submitted travel text.
            raise ModelUnavailable("The model could not complete this message. No trip changes were saved.") from exc
