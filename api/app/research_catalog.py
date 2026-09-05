"""Offline, review-gated research catalogue utilities.

This module deliberately does not implement a ``CorpusRepository``. Catalogue
records are discovery and review-preparation material until a later retrieval
phase consumes approved entries without changing audit verdicts.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from app.case_maps import CaseMapValidator
from app.models import Authority, CaseMapDetail
from app.parsers import normalise_citation
from app.taxonomy import PROPOSITIONS

CATALOGUE_VERSION = "v1"
CATALOGUE_TOOL_VERSION = "proofmark-research-catalog.1"
APPROVED_AUTHORITIES_FILENAME = "approved_authorities.json"
MANIFEST_FILENAME = "catalogue_manifest.json"
OFFICIAL_HOST = "www.elitigation.sg"

RESTRAINT_TERMS = (
    "restraint of trade",
    "restrictive covenant",
    "non-compete",
    "non compete",
    "non-solicitation",
    "non solicitation",
    "non-dealing",
    "non dealing",
    "legitimate proprietary interest",
    "customer connection",
    "trained workforce",
    "blue pencil",
    "employment restraint",
)

NUMBERED_PARAGRAPH = re.compile(r"^\[\d+(?:[-–]\d+)?\]$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SINGAPORE_CITATION = re.compile(r"^\[\d{4}\]\s*SG(?:CA|CAI|HC(?:\([A-Z]\))?|HCF|HCR)\s+\d+$", re.IGNORECASE)


class CatalogueValidationError(ValueError):
    """Raised when a catalogue cannot safely be used as reviewed research data."""


def canonical_json_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogueValidationError(f"Cannot read {path.name}: {exc}") from exc


def _parse_datetime(value: object, field_name: str) -> None:
    if not isinstance(value, str):
        raise CatalogueValidationError(f"{field_name} must be an ISO timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CatalogueValidationError(f"{field_name} must be an ISO timestamp") from exc


def _require_sha(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not SHA256.fullmatch(value.lower()):
        raise CatalogueValidationError(f"{field_name} must be a SHA-256 hash")


def _validate_manifest(manifest: object, authorities: object, *, require_ready: bool) -> dict[str, object]:
    if not isinstance(manifest, dict):
        raise CatalogueValidationError("catalogue manifest must be an object")
    if manifest.get("catalogue_version") != CATALOGUE_VERSION:
        raise CatalogueValidationError(f"catalogue_version must be {CATALOGUE_VERSION}")
    status = manifest.get("status")
    if status not in {"awaiting_legal_review", "ready"}:
        raise CatalogueValidationError("catalogue status must be awaiting_legal_review or ready")
    _parse_datetime(manifest.get("generated_at"), "manifest generated_at")
    if manifest.get("build_tool_version") != CATALOGUE_TOOL_VERSION:
        raise CatalogueValidationError("catalogue build_tool_version is unsupported")
    datasets = manifest.get("source_datasets")
    if not isinstance(datasets, list) or not datasets:
        raise CatalogueValidationError("catalogue manifest requires source_datasets")
    for source in datasets:
        if not isinstance(source, dict):
            raise CatalogueValidationError("source dataset must be an object")
        for key in ("name", "licence", "source_url", "sha256"):
            if not source.get(key):
                raise CatalogueValidationError(f"source dataset requires {key}")
        _require_sha(source["sha256"], "source dataset sha256")
    if not isinstance(authorities, list):
        raise CatalogueValidationError("approved_authorities.json must be an array")
    if manifest.get("approved_authority_count") != len(authorities):
        raise CatalogueValidationError("approved_authority_count does not match the authority file")
    if manifest.get("approved_authorities_sha256") != canonical_json_hash(authorities):
        raise CatalogueValidationError("approved_authorities_sha256 does not match the authority file")
    if require_ready and status != "ready":
        raise CatalogueValidationError("catalogue is not ready for a product review gate")
    if status == "ready" and len(authorities) != 25:
        raise CatalogueValidationError("a ready v1 catalogue must contain exactly 25 reviewed authorities")
    return manifest


def _validate_authority_record(record: object) -> dict[str, object]:
    if not isinstance(record, dict):
        raise CatalogueValidationError("catalogue authority must be an object")
    for key in ("catalogue_id", "candidate_name", "discovery", "authority", "case_map", "treatment_status"):
        if not record.get(key):
            raise CatalogueValidationError(f"catalogue authority requires {key}")
    discovery = record["discovery"]
    if not isinstance(discovery, dict):
        raise CatalogueValidationError("discovery must be an object")
    for key in ("source_dataset", "citing_judgments", "matched_terms", "suggested_propositions"):
        if key not in discovery:
            raise CatalogueValidationError(f"discovery requires {key}")
    if not isinstance(discovery["citing_judgments"], list) or not discovery["citing_judgments"]:
        raise CatalogueValidationError("discovery requires at least one citing judgment provenance record")
    if not set(discovery["suggested_propositions"]).issubset(PROPOSITIONS):
        raise CatalogueValidationError("discovery contains a proposition outside the controlled taxonomy")
    try:
        authority = Authority.model_validate(record["authority"])
        case_map = CaseMapDetail.model_validate(record["case_map"])
    except ValueError as exc:
        raise CatalogueValidationError(f"invalid authority or Case Map: {exc}") from exc
    if authority.source_provenance != "officially_sourced":
        raise CatalogueValidationError("catalogue authority must be officially_sourced")
    if urlparse(authority.official_url).hostname != OFFICIAL_HOST:
        raise CatalogueValidationError("catalogue authority must use an eLitigation official URL")
    _require_sha(authority.document_hash, "authority document_hash")
    if not authority.passages or any(not NUMBERED_PARAGRAPH.fullmatch(item.paragraph_label) for item in authority.passages):
        raise CatalogueValidationError("catalogue authority requires exact numbered paragraphs")
    if normalise_citation(authority.citation) != authority.citation_key:
        raise CatalogueValidationError("authority citation_key does not match its citation")
    if case_map.status != "approved" or case_map.reviewer_id is None or case_map.reviewed_at is None:
        raise CatalogueValidationError("catalogue authority requires a reviewer-approved Case Map")
    if case_map.citation_key != authority.citation_key or case_map.document_hash != authority.document_hash:
        raise CatalogueValidationError("Case Map must match the authority citation and document hash")
    if not case_map.annotations or any(annotation.review_status != "approved" for annotation in case_map.annotations):
        raise CatalogueValidationError("catalogue authority requires approved Case Map annotations")
    source_by_label = {item.paragraph_label: item.text for item in authority.passages}
    if {item.paragraph_label: item.text for item in case_map.source_paragraphs} != source_by_label:
        raise CatalogueValidationError("Case Map source paragraphs must exactly match authority paragraphs")
    _, errors = CaseMapValidator().validate(authority, case_map.annotations)
    if errors:
        raise CatalogueValidationError(f"Case Map anchor validation failed: {errors[0]}")
    if record["treatment_status"] not in {"current_reviewed", "negative_treatment", "not_verified"}:
        raise CatalogueValidationError("invalid treatment_status")
    return record


def load_catalogue(directory: Path, *, require_ready: bool = False) -> list[dict[str, object]]:
    """Load and validate a catalogue without registering it as runtime evidence."""

    manifest = _read_json(directory / MANIFEST_FILENAME)
    authorities = _read_json(directory / APPROVED_AUTHORITIES_FILENAME)
    _validate_manifest(manifest, authorities, require_ready=require_ready)
    assert isinstance(authorities, list)
    validated = [_validate_authority_record(item) for item in authorities]
    citation_keys = [Authority.model_validate(item["authority"]).citation_key for item in validated]
    if len(citation_keys) != len(set(citation_keys)):
        raise CatalogueValidationError("catalogue may not contain duplicate authority citations")
    return validated


@dataclass
class _CandidateAggregate:
    candidate_name: str
    candidate_citation: str
    matched_terms: set[str] = field(default_factory=set)
    citing_judgments: dict[str, str] = field(default_factory=dict)
    propositions: Counter[str] = field(default_factory=Counter)
    matches: int = 0


def _suggest_propositions(text: str) -> set[str]:
    lowered = text.casefold()
    suggestions = set()
    mapping = {
        "legitimate proprietary interest": "legitimate_proprietary_interest",
        "customer connection": "customer_connections",
        "trained workforce": "stable_trained_workforce",
        "non-compete": "activity_scope",
        "non compete": "activity_scope",
        "non-solicitation": "non_solicitation_non_dealing",
        "non solicitation": "non_solicitation_non_dealing",
        "non-dealing": "non_solicitation_non_dealing",
        "non dealing": "non_solicitation_non_dealing",
        "blue pencil": "severance_blue_pencil",
    }
    for phrase, proposition in mapping.items():
        if phrase in lowered:
            suggestions.add(proposition)
    return suggestions


def _case_name_key(value: str) -> str:
    """Match dataset titles despite its frequently abbreviated cited citations."""

    without_citation = re.sub(r"\s*\[\d{4}\].*$", "", value)
    return re.sub(r"[^a-z0-9]+", "", without_citation.casefold())


def _iter_rows(dataset_path: Path, fields: tuple[str, ...], chunk_size: int):
    with dataset_path.open("r", encoding="latin-1", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not set(fields).issubset(reader.fieldnames):
            raise ValueError("dataset is missing required SG-LegalCite columns")
        while True:
            batch = [next(reader, None) for _ in range(chunk_size)]
            batch = [row for row in batch if row is not None]
            if not batch:
                return
            yield from batch


def build_shortlist(dataset_path: Path, *, limit: int = 100, chunk_size: int = 5_000) -> dict[str, object]:
    """Stream SG-LegalCite into metadata-only research leads.

    The source CSV is decoded as Latin-1 and processed in fixed-size chunks.
    Its nearby citation paragraph is searched for discovery only and is never
    emitted in the output artifact.
    """

    if limit < 1 or chunk_size < 1:
        raise ValueError("limit and chunk_size must be positive")
    aggregates: dict[str, _CandidateAggregate] = {}
    fields = (
        "Judgment_URL",
        "Judgment_Reference",
        "Case Name",
        "Key Principles Illustrated",
        "Issue",
        "Issue Group",
        "Cited Case",
        "Paragraph",
    )
    singapore_cases: dict[str, str] = {}
    for row in _iter_rows(dataset_path, fields, chunk_size):
        citation = (row.get("Judgment_Reference") or "").strip()
        case_name = (row.get("Case Name") or "").strip()
        if case_name and SINGAPORE_CITATION.fullmatch(citation):
            singapore_cases.setdefault(_case_name_key(case_name), citation)
    for row in _iter_rows(dataset_path, fields, chunk_size):
        searchable = " ".join(row.get(field, "") or "" for field in fields)
        lowered = searchable.casefold()
        matched_terms = {term for term in RESTRAINT_TERMS if term in lowered}
        if not matched_terms:
            continue
        candidate_name = (row.get("Cited Case") or "").strip()
        candidate_citation = singapore_cases.get(_case_name_key(candidate_name))
        if not candidate_name or not candidate_citation:
            continue
        key = normalise_citation(candidate_citation)
        aggregate = aggregates.setdefault(
            key,
            _CandidateAggregate(candidate_name=candidate_name, candidate_citation=candidate_citation),
        )
        aggregate.matches += 1
        aggregate.matched_terms.update(matched_terms)
        aggregate.propositions.update(_suggest_propositions(searchable))
        citation = (row.get("Judgment_Reference") or "").strip()
        url = (row.get("Judgment_URL") or "").strip()
        if citation and url and len(aggregate.citing_judgments) < 5:
            aggregate.citing_judgments[citation] = url
    ordered = sorted(aggregates.values(), key=lambda item: (-item.matches, item.candidate_name.casefold()))[:limit]
    return {
        "catalogue_version": CATALOGUE_VERSION,
        "build_tool_version": CATALOGUE_TOOL_VERSION,
        "source_dataset": dataset_path.name,
        "runtime_use": "research_only_not_loaded_by_active_corpus",
        "candidates": [
            {
                "candidate_name": item.candidate_name,
                "candidate_citation": item.candidate_citation,
                "match_count": item.matches,
                "matched_terms": sorted(item.matched_terms),
                "suggested_propositions": sorted(item.propositions),
                "citing_judgments": [
                    {"citation": citation, "official_url": url} for citation, url in sorted(item.citing_judgments.items())
                ],
            }
            for item in ordered
        ],
    }
