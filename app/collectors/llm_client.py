import logging
import time
from typing import Protocol, Type, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Raised when a provider call fails after retries are exhausted."""


class LLMClient(Protocol):
    def generate_json(self, system_prompt: str, user_prompt: str, schema: Type[T]) -> T:
        """Call the model and return a validated instance of `schema`."""
        ...


class GeminiClient:
    def __init__(self, api_key: str, model: str, requests_per_minute: int, max_retries: int = 3):
        if not api_key:
            raise LLMError(
                "GEMINI_API_KEY is not set. Get a free key at https://aistudio.google.com/apikey "
                "and put it in your .env file."
            )
        # Imported here rather than at module level: this way, choosing a
        # different LLM_PROVIDER doesn't require google-genai to even be
        # installed.
        from google import genai
        self._genai = genai
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._min_interval = 60.0 / requests_per_minute
        self._max_retries = max_retries
        self._last_call_at = 0.0

    def _wait_for_rate_limit(self):
        elapsed = time.monotonic() - self._last_call_at
        remaining = self._min_interval - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def generate_json(self, system_prompt: str, user_prompt: str, schema: Type[T]) -> T:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=schema,
        )

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            self._wait_for_rate_limit()
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=user_prompt,
                    config=config,
                )
                self._last_call_at = time.monotonic()
                if response.parsed is None:
                    raise LLMError(f"Gemini returned no parseable JSON (raw text: {response.text!r})")
                return response.parsed
            except Exception as exc:
                self._last_call_at = time.monotonic()
                last_error = exc
                # Rate-limit errors are the one case worth retrying with
                # backoff; anything else (bad key, malformed schema, etc.)
                # will just fail the same way again.
                is_rate_limit = "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)
                if is_rate_limit and attempt < self._max_retries:
                    backoff = 2 ** attempt
                    logger.warning("Gemini rate-limited (attempt %d/%d), backing off %ds", attempt, self._max_retries, backoff)
                    time.sleep(backoff)
                    continue
                break

        raise LLMError(f"Gemini call failed after {self._max_retries} attempt(s): {last_error}")


def get_llm_client(settings) -> LLMClient:
    provider = settings.llm_provider.lower()

    if provider == "gemini":
        return GeminiClient(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            requests_per_minute=settings.gemini_requests_per_minute,
        )
    if provider == "openai":
        raise NotImplementedError(
            "LLM_PROVIDER=openai is planned but not implemented yet - only Gemini is wired up so far."
        )
    if provider == "anthropic":
        raise NotImplementedError(
            "LLM_PROVIDER=anthropic is planned but not implemented yet - only Gemini is wired up so far."
        )

    raise ValueError(f"Unknown LLM_PROVIDER '{settings.llm_provider}' - expected 'gemini', 'openai', or 'anthropic'.")