"""Validated, presentation-only metadata for browsing official authorities."""

from __future__ import annotations

import json
from pathlib import Path

from app.models import Authority, AuthoritySearchMetadata, AuthorityView
from app.taxonomy import PROPOSITIONS


class AuthoritySearchMetadataError(ValueError):
    """Raised when curated search metadata cannot be displayed safely."""


class AuthoritySearchMetadataRepository:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(__file__).resolve().parents[1] / "data" / "authority_search_metadata.json"
        self._records = self._load()

    def _load(self) -> dict[str, AuthoritySearchMetadata]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AuthoritySearchMetadataError(f"Cannot read authority search metadata: {exc}") from exc
        if not isinstance(raw, list):
            raise AuthoritySearchMetadataError("authority search metadata must be an array")

        records: dict[str, AuthoritySearchMetadata] = {}
        for value in raw:
            try:
                record = AuthoritySearchMetadata.model_validate(value)
            except ValueError as exc:
                raise AuthoritySearchMetadataError(f"Invalid authority search metadata: {exc}") from exc
            if record.citation_key in records:
                raise AuthoritySearchMetadataError(f"Duplicate authority search metadata: {record.citation_key}")
            unknown_tags = set(record.issue_tags) - PROPOSITIONS
            if unknown_tags:
                raise AuthoritySearchMetadataError(
                    f"{record.citation_key}: unknown issue tag {sorted(unknown_tags)[0]}"
                )
            if record.review_status == "approved" and (not record.reviewer or not record.reviewed_at):
                raise AuthoritySearchMetadataError(
                    f"{record.citation_key}: approved metadata requires reviewer and reviewed_at"
                )
            if record.review_status == "pending" and (record.reviewer or record.reviewed_at):
                raise AuthoritySearchMetadataError(
                    f"{record.citation_key}: pending metadata cannot claim reviewer approval"
                )
            records[record.citation_key] = record
        return records

    def decorate(self, authorities: list[Authority]) -> list[AuthorityView]:
        return [
            AuthorityView.model_validate(
                {**authority.model_dump(mode="json"), "search_metadata": self._records.get(authority.citation_key)}
            )
            for authority in authorities
        ]
