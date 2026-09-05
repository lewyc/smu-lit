from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from app.config import Settings
from app.models import GeminiClaims, ParsedClaim, ParserMode
from app.taxonomy import OVERGENERALISATION_TERMS, PROPOSITIONS, proposition_for

CITATION_PATTERN = re.compile(
    r"\[(?P<year>\d{4})\]\s*(?P<court>SG[A-Z()]+)\s*(?P<number>\d+)",
    re.IGNORECASE,
)
PINPOINT_PATTERN = re.compile(r"(?:at\s*)?\[(?P<pin>\d+(?:[-–]\d+)?)\]", re.IGNORECASE)


def normalise_citation(value: str) -> str:
    match = CITATION_PATTERN.search(value)
    if not match:
        return re.sub(r"[^A-Z0-9]", "", value.upper())
    return f"{match.group('year')}{match.group('court').upper()}{match.group('number')}"


def canonical_citation(value: str) -> str | None:
    match = CITATION_PATTERN.search(value)
    if not match:
        return None
    return f"[{match.group('year')}] {match.group('court').upper()} {match.group('number')}"


class ClaimParser(Protocol):
    def parse(self, text: str) -> list[ParsedClaim]: ...


class LocalClaimParser:
    @staticmethod
    def _sentences(text: str) -> list[str]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        sentences: list[str] = []
        for line in lines:
            sentences.extend(part.strip() for part in re.split(r"(?<=[.!?])\s+", line) if part.strip())
        return sentences

    def parse(self, text: str) -> list[ParsedClaim]:
        claims: list[ParsedClaim] = []
        for order, sentence in enumerate(self._sentences(text), start=1):
            citation_match = CITATION_PATTERN.search(sentence)
            citation = canonical_citation(citation_match.group(0)) if citation_match else None
            pinpoint = None
            if citation_match:
                tail = sentence[citation_match.end() :]
                pin_match = PINPOINT_PATTERN.search(tail)
                pinpoint = f"[{pin_match.group('pin')}]" if pin_match else None
            proposition, confidence = proposition_for(sentence)
            lowered = sentence.lower()
            terms = [term for term in OVERGENERALISATION_TERMS if term in lowered]
            if re.search(r"\ball\b.{0,60}\bnon-competes?\b", lowered) and "all non-competes" not in terms:
                terms.append("all non-competes")
            claims.append(
                ParsedClaim(
                    order=order,
                    text=sentence,
                    citation=citation,
                    pinpoint=pinpoint,
                    proposition=proposition,
                    parser_confidence=confidence,
                    parser_used="local",
                    overgeneralisation_terms=terms,
                )
            )
        return claims


class GeminiClaimParser:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def parse(self, text: str) -> list[ParsedClaim]:
        from google import genai
        from google.genai import types

        prompt = (
            "Atomise this answer into legal claims. Extract only citations present in the "
            "answer. Choose exactly one proposition from this controlled taxonomy: "
            f"{sorted(PROPOSITIONS)}. Do not assess truth, support, or verdict.\n\n{text}"
        )
        client = genai.Client(
            api_key=self.settings.gemini_api_key,
            http_options=types.HttpOptions(
                timeout=int(self.settings.gemini_timeout_seconds * 1000)
            ),
        )
        response = client.models.generate_content(
            model=self.settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GeminiClaims,
                temperature=0,
            ),
        )
        parsed = response.parsed
        if not isinstance(parsed, GeminiClaims) or not parsed.claims:
            raise ValueError("Gemini returned no schema-valid claims")
        claims: list[ParsedClaim] = []
        for item in parsed.claims:
            if item.proposition not in PROPOSITIONS:
                raise ValueError("Gemini returned a proposition outside the controlled taxonomy")
            payload = item.model_dump()
            payload["citation"] = canonical_citation(item.citation) if item.citation else None
            claims.append(
                ParsedClaim(
                    **payload,
                    parser_used="gemini",
                )
            )
        return claims


@dataclass(frozen=True)
class ParseResult:
    claims: list[ParsedClaim]
    parser_used: str
    fallback_reason: str | None


def parse_with_mode(text: str, mode: ParserMode, settings: Settings) -> ParseResult:
    local = LocalClaimParser()
    if mode == "local":
        return ParseResult(local.parse(text), "local", None)
    if not settings.gemini_api_key:
        reason = "Gemini API key is not configured; local parser used."
        return ParseResult(local.parse(text), "local", reason if mode != "local" else None)
    try:
        claims = GeminiClaimParser(settings).parse(text)
        return ParseResult(claims, "gemini", None)
    except Exception as exc:
        safe_reason = f"Gemini unavailable ({type(exc).__name__}); local parser used."
        return ParseResult(local.parse(text), "local", safe_reason)
