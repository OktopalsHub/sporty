from __future__ import annotations

import json
from typing import Any

import httpx


class GeminiError(RuntimeError):
    """Raised when Gemini analysis cannot be completed."""


class GeminiClient:
    """Small Gemini adapter returning validated structured analysis.

    Gemini is used only for analysis. It never chooses booking IDs, places bets,
    or bypasses the prediction/ticket validation layer.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def analyze(self, context: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            "Analyze this football betting candidate using only the supplied data. "
            "Return JSON with exactly these fields: probability (number 0 to 1), "
            "confidence (low|medium|high|very_high), reasons (array of short strings). "
            "Do not invent injuries, form, statistics, or facts not supplied. "
            "This is analysis only, not a bet placement decision.\n\n"
            f"{json.dumps(context, default=str)}"
        )
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        url = f"{self.base_url}/models/{self.model}:generateContent"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    params={"key": self.api_key},
                    json=body,
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise GeminiError("Gemini analysis request failed") from exc

        try:
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
            result = json.loads(text)
            probability = float(result["probability"])
            confidence = str(result["confidence"])
            reasons = tuple(str(item) for item in result["reasons"])
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise GeminiError("Gemini returned an invalid analysis response") from exc

        if not 0.0 <= probability <= 1.0:
            raise GeminiError("Gemini probability must be between 0 and 1")
        if confidence not in {"low", "medium", "high", "very_high"}:
            raise GeminiError("Gemini confidence is invalid")
        if not reasons:
            raise GeminiError("Gemini must provide at least one reason")

        return {
            "probability": probability,
            "confidence": confidence,
            "reasons": reasons,
        }
