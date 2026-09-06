"""Bounded structured-output adapters for optional model-assisted labelling.

The audit engine never relies on this module for legal verdicts.  It only
returns data that is subsequently constrained by the caller's deterministic
validation rules.
"""

from __future__ import annotations

import json

import httpx
from pydantic import BaseModel

from app.config import Settings

OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"


def generate_structured(
    settings: Settings,
    *,
    model: str,
    prompt: str,
    response_schema: type[BaseModel],
) -> BaseModel:
    """Generate schema-constrained data without logging prompts, output, or keys.

    OpenRouter is preferred when configured so a project can use a single
    OpenRouter key for Gemini Flash Lite.  Direct Gemini remains available for
    backwards compatibility.
    """
    if settings.openrouter_api_key:
        return _from_openrouter(settings, model=model, prompt=prompt, response_schema=response_schema)
    if settings.gemini_api_key:
        return _from_gemini(settings, model=model, prompt=prompt, response_schema=response_schema)
    raise RuntimeError("No structured-model API key is configured")


def _from_openrouter(
    settings: Settings,
    *,
    model: str,
    prompt: str,
    response_schema: type[BaseModel],
) -> BaseModel:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return only the requested JSON object. Never invent case names, "
                    "citations, paragraph labels, quotations, or judgment text."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": response_schema.__name__.lower(),
                "strict": True,
                "schema": response_schema.model_json_schema(),
            },
        },
        # Avoid silently routing to a provider that cannot honour JSON Schema.
        "provider": {"require_parameters": True},
    }
    response = httpx.post(
        OPENROUTER_CHAT_COMPLETIONS_URL,
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5173",
            "X-OpenRouter-Title": "VERITAS",
        },
        json=payload,
        timeout=settings.gemini_timeout_seconds,
    )
    response.raise_for_status()
    body = response.json()
    try:
        content = body["choices"][0]["message"]["content"]
    except (IndexError, KeyError, TypeError) as exc:
        raise ValueError("OpenRouter returned no structured response content") from exc
    if not isinstance(content, str):
        content = json.dumps(content)
    return response_schema.model_validate_json(content)


def _from_gemini(
    settings: Settings,
    *,
    model: str,
    prompt: str,
    response_schema: type[BaseModel],
) -> BaseModel:
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(timeout=int(settings.gemini_timeout_seconds * 1000)),
    )
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=0,
        ),
    )
    if not isinstance(response.parsed, response_schema):
        raise ValueError("Direct Gemini returned no schema-valid response")
    return response.parsed
