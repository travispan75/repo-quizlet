import json
import os
import threading
import time
from collections import deque
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


_DEFAULT_MODEL = "gpt-4o-mini"
_DEFAULT_TPM = 180_000
_OUTPUT_RESERVE = 4_000
_MAX_OUTPUT_TOKENS = 16_384
_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"


def _estimate_tokens(prompt: str) -> int:
    return max(1, len(prompt) // 3) + _OUTPUT_RESERVE


class RateLimiter:
    def __init__(self, tpm: int) -> None:
        self._tpm = tpm
        self._events: deque[tuple[float, int]] = deque()
        self._lock = threading.Lock()

    def acquire(self, tokens: int) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                while self._events and now - self._events[0][0] >= 60.0:
                    self._events.popleft()
                used = sum(t for _, t in self._events)
                if not self._events or used + tokens <= self._tpm:
                    self._events.append((now, tokens))
                    return
                wait = 60.0 - (now - self._events[0][0])
            time.sleep(max(wait, 0.1))


class OpenAIClient:
    # Single process-wide limiter so concurrent stages share one TPM budget.
    _shared_limiter: RateLimiter | None = None
    _shared_limiter_lock = threading.Lock()

    def __init__(
        self,
        api_key: str | None = None,
        model: str = _DEFAULT_MODEL,
        tpm: int = _DEFAULT_TPM,
    ) -> None:
        if api_key is None:
            load_dotenv(_ENV_PATH)
            api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set in environment or any discoverable .env")
        self._client = OpenAI(api_key=api_key)
        self._model = model
        with OpenAIClient._shared_limiter_lock:
            if OpenAIClient._shared_limiter is None:
                OpenAIClient._shared_limiter = RateLimiter(tpm)
            self._limiter = OpenAIClient._shared_limiter

    def generate(self, prompt: str) -> str:
        self._limiter.acquire(_estimate_tokens(prompt))
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=_MAX_OUTPUT_TOKENS,
        )
        return (response.choices[0].message.content or "").strip()

    def generate_json(self, prompt: str, schema: dict | None = None) -> dict:
        if schema is not None:
            response_format = {"type": "json_schema", "json_schema": schema}
        else:
            response_format = {"type": "json_object"}
        self._limiter.acquire(_estimate_tokens(prompt))
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            response_format=response_format,
            max_tokens=_MAX_OUTPUT_TOKENS,
        )
        text = (response.choices[0].message.content or "").strip()
        return json.loads(text)
