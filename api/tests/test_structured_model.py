from pydantic import BaseModel

from app.config import Settings
from app.models import GeminiClaim, GeminiClaims
from app.parsers import parse_with_mode
from app.structured_model import OPENROUTER_CHAT_COMPLETIONS_URL, generate_structured


class ExampleSchema(BaseModel):
    label: str


def test_openrouter_is_preferred_and_requests_strict_schema(monkeypatch) -> None:
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": '{"label":"anchored"}'}}]}

    def fake_post(url, *, headers, json, timeout):
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("app.structured_model.httpx.post", fake_post)
    settings = Settings(
        OPENROUTER_API_KEY="test-openrouter-key",
        GEMINI_API_KEY="test-direct-key",
    )

    result = generate_structured(
        settings,
        model=settings.claim_model,
        prompt="Return a schema-bound label.",
        response_schema=ExampleSchema,
    )

    assert result == ExampleSchema(label="anchored")
    assert settings.structured_model_provider == "openrouter"
    assert settings.claim_model == "google/gemini-3.5-flash-lite"
    assert captured["url"] == OPENROUTER_CHAT_COMPLETIONS_URL
    assert captured["headers"]["Authorization"] == "Bearer test-openrouter-key"
    assert captured["json"]["response_format"]["json_schema"]["strict"] is True
    assert captured["json"]["provider"] == {"require_parameters": True}


def test_claim_parser_records_openrouter_provenance(monkeypatch) -> None:
    def fake_generate(*_args, **_kwargs):
        return GeminiClaims(
            claims=[
                GeminiClaim(
                    order=1,
                    text="The restraint needs a legitimate proprietary interest [2007] SGCA 53.",
                    citation="[2007] SGCA 53",
                    proposition="legitimate_proprietary_interest",
                    parser_confidence=0.9,
                )
            ]
        )

    monkeypatch.setattr("app.parsers.generate_structured", fake_generate)
    result = parse_with_mode(
        "The restraint needs a legitimate proprietary interest [2007] SGCA 53.",
        "auto",
        Settings(OPENROUTER_API_KEY="test-openrouter-key"),
    )

    assert result.parser_used == "openrouter"
    assert result.claims[0].parser_used == "openrouter"
