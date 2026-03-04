"""
core/llm.py — Gemini provider abstraction.

Single seam for all LLM interaction. CLI commands call this module,
never the google-genai SDK directly.
"""

from __future__ import annotations

from google import genai
from google.genai import types

from azathoth.config import config


class LLMError(Exception):
    """Raised when the LLM call fails."""


async def generate(
    system_prompt: str,
    user_message: str,
    *,
    json_mode: bool = False,
) -> str:
    """Send a prompt to Gemini and return the raw text response.

    Args:
        system_prompt: The system instruction that frames the model's behavior.
        user_message:  The user-facing content (e.g. a git diff).
        json_mode:     When True, constrains the model to emit valid JSON.

    Returns:
        The model's text response (caller is responsible for parsing).

    Raises:
        LLMError: On any SDK or network failure.
    """
    api_key = config.gemini_api_key.get_secret_value()
    if not api_key:
        raise LLMError(
            "Gemini API key not set. Export GEMINI_API_KEY or AZATHOTH_GEMINI_API_KEY."
        )

    try:
        client = genai.Client(api_key=api_key)

        gen_config = types.GenerateContentConfig(
            system_instruction=system_prompt,
        )
        if json_mode:
            gen_config.response_mime_type = "application/json"

        response = client.models.generate_content(
            model=config.gemini_model,
            contents=user_message,
            config=gen_config,
        )

        if not response.text:
            raise LLMError("Gemini returned an empty response.")

        return response.text

    except LLMError:
        raise
    except Exception as exc:
        raise LLMError(f"Gemini API call failed: {exc}") from exc
