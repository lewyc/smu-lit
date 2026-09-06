"""Fail-closed validation for runtime judgment snapshots.

The runtime loader and release tooling share this module so a file cannot pass
the command-line gate and then be interpreted differently by the API.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from app.models import Authority, CorpusMetadata
from app.parsers import normalise_citation
from app.taxonomy import PROPOSITIONS

OFFICIAL_HOSTS = frozenset({"www.elitigation.sg", "elitigation.sg"})
NEUTRAL_CITATION = re.compile(r"^\[\d{4}\]\s+SG[A-Z()]+\s+\d+$", re.IGNORECASE)
PARAGRAPH_LABEL = re.compile(r"^\[(\d{1,4})\](?:-\[(\d{1,4})\])?$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class SnapshotValidationError(ValueError):
    """Raised when source data is unsafe to expose to the audit engine."""


def canonical_authority_hash(authorities: list[Authority]) -> str:
    payload = json.dumps([authority.model_dump(mode="json") for authority in authorities], sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_snapshot(path: Path) -> tuple[CorpusMetadata, list[Authority], bytes]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
        metadata = CorpusMetadata.model_validate(payload["metadata"])
        authorities = [Authority.model_validate(item) for item in payload["authorities"]]
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise SnapshotValidationError(f"invalid snapshot: {exc}") from exc
    validate_snapshot_records(metadata, authorities)
    return metadata, authorities, raw


def validate_snapshot_records(
    metadata: CorpusMetadata,
    authorities: list[Authority],
    *,
    require_certified: bool = False,
) -> None:
    if not authorities:
        raise SnapshotValidationError("snapshot contains no authorities")
    if metadata.authority_count != len(authorities):
        raise SnapshotValidationError("metadata authority count does not match snapshot contents")
    passage_count = sum(len(item.passages) for item in authorities)
    if metadata.passage_count != passage_count:
        raise SnapshotValidationError("metadata passage count does not match snapshot contents")
    if metadata.content_hash != canonical_authority_hash(authorities):
        raise SnapshotValidationError("metadata content hash does not match snapshot contents")
    if metadata.source_status != "officially_sourced":
        raise SnapshotValidationError("runtime snapshot must be officially sourced")

    authority_ids: set[str] = set()
    citation_keys: set[str] = set()
    passage_ids: set[str] = set()
    for authority in authorities:
        _validate_authority(authority, authority_ids, citation_keys, passage_ids, require_certified=require_certified)


def _validate_authority(
    authority: Authority,
    authority_ids: set[str],
    citation_keys: set[str],
    passage_ids: set[str],
    *,
    require_certified: bool,
) -> None:
    if authority.id in authority_ids:
        raise SnapshotValidationError(f"duplicate authority id: {authority.id}")
    authority_ids.add(authority.id)
    if authority.citation_key in citation_keys:
        raise SnapshotValidationError(f"duplicate authority citation: {authority.citation}")
    citation_keys.add(authority.citation_key)

    if not NEUTRAL_CITATION.fullmatch(authority.citation):
        raise SnapshotValidationError(f"{authority.citation}: malformed neutral citation")
    if normalise_citation(authority.citation) != authority.citation_key:
        raise SnapshotValidationError(f"{authority.citation}: citation key does not match the citation")
    if normalise_citation(authority.case_name) == authority.citation_key:
        raise SnapshotValidationError(f"{authority.citation}: case name is only a citation, not canonical identity metadata")
    if not authority.case_name.strip() or not authority.court.strip():
        raise SnapshotValidationError(f"{authority.citation}: missing canonical case identity metadata")
    if authority.decision_date.year != int(authority.citation[1:5]):
        raise SnapshotValidationError(f"{authority.citation}: decision date year conflicts with the citation")

    parsed_url = urlparse(authority.official_url)
    if parsed_url.scheme != "https" or parsed_url.hostname not in OFFICIAL_HOSTS:
        raise SnapshotValidationError(f"{authority.citation}: official URL is not an eLitigation HTTPS URL")
    if authority.source_host and authority.source_host != parsed_url.hostname:
        raise SnapshotValidationError(f"{authority.citation}: source host conflicts with the official URL")
    if authority.source_provenance != "officially_sourced":
        raise SnapshotValidationError(f"{authority.citation}: snapshot evidence is not officially sourced")
    if not authority.document_hash or not SHA256.fullmatch(authority.document_hash):
        raise SnapshotValidationError(f"{authority.citation}: missing SHA-256 document hash")
    if not authority.passages:
        raise SnapshotValidationError(f"{authority.citation}: no judgment paragraphs were retained")
    if require_certified and (
        authority.source_review_status != "approved" or not authority.source_reviewer or not authority.source_reviewed_at
    ):
        raise SnapshotValidationError(f"{authority.citation}: missing approved source-review metadata")

    authority_year = int(authority.citation[1:5])
    labels: set[str] = set()
    for passage in authority.passages:
        match = PARAGRAPH_LABEL.fullmatch(passage.paragraph_label)
        if not match:
            raise SnapshotValidationError(
                f"{authority.citation}: invalid paragraph label {passage.paragraph_label!r}"
            )
        numbers = [int(value) for value in match.groups() if value is not None]
        if authority_year in numbers:
            raise SnapshotValidationError(
                f"{authority.citation}: neutral-citation year {passage.paragraph_label} was misread as a paragraph"
            )
        if passage.paragraph_label in labels:
            raise SnapshotValidationError(
                f"{authority.citation}: duplicate paragraph label {passage.paragraph_label}"
            )
        labels.add(passage.paragraph_label)
        if passage.id in passage_ids:
            raise SnapshotValidationError(f"duplicate passage id: {passage.id}")
        passage_ids.add(passage.id)
        if not passage.text.strip():
            raise SnapshotValidationError(f"{authority.citation} {passage.paragraph_label}: empty judgment text")
        if not set(passage.supported_propositions).issubset(PROPOSITIONS):
            raise SnapshotValidationError(
                f"{authority.citation} {passage.paragraph_label}: proposition is outside the controlled taxonomy"
            )
        if passage.source_provenance != "officially_sourced":
            raise SnapshotValidationError(
                f"{authority.citation} {passage.paragraph_label}: passage is not officially sourced"
            )
        if require_certified:
            if passage.assessment_status != "human_reviewed":
                raise SnapshotValidationError(
                    f"{authority.citation} {passage.paragraph_label}: evidence is not human reviewed"
                )
            if not passage.source_role_reviewed or passage.source_role == "unreviewed" or not passage.source_role_reviewer:
                raise SnapshotValidationError(
                    f"{authority.citation} {passage.paragraph_label}: source role is not reviewed"
                )
