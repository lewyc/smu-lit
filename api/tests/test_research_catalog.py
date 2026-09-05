import csv
import json
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.case_maps import CaseMapService
from app.config import Settings
from app.corpus import ActiveCorpusRepository
from app.models import Authority, Passage
from app.research_catalog import CATALOGUE_TOOL_VERSION, CatalogueValidationError, build_shortlist, canonical_json_hash, load_catalogue


def _authority() -> Authority:
    return Authority(
        id="catalogue-authority",
        citation="[2025] SGHC 1",
        citation_key="2025SGHC1",
        case_name="Employer Pte Ltd v Employee",
        court="High Court",
        decision_date=date(2025, 1, 1),
        official_url="https://www.elitigation.sg/gd/s/2025_SGHC_1",
        source_provenance="officially_sourced",
        assessment_status="ai_supported",
        document_hash="a" * 64,
        passages=[
            Passage(
                id="catalogue-10",
                paragraph_label="[10]",
                text="The employer must identify a legitimate proprietary interest, subject to the facts.",
                supported_propositions=["legitimate_proprietary_interest"],
                limitations=["Fact-sensitive."],
                source_provenance="officially_sourced",
                assessment_status="ai_supported",
            )
        ],
    )


def _write_catalogue(directory: Path) -> Path:
    authority = _authority()
    corpus = ActiveCorpusRepository(directory / "not-runtime-snapshot.json")
    corpus.activate([authority], persist_snapshot=False)
    service = CaseMapService(Settings(PROOFMARK_DATA_MODE="demo"), corpus)
    approved_map = service.approve(service.generate(authority.citation).public_id, reviewer_id=uuid4())
    authorities = [
        {
            "catalogue_id": "catalogue-2025sghc1",
            "candidate_name": authority.case_name,
            "discovery": {
                "source_dataset": "SG-LegalCite",
                "citing_judgments": [{"citation": "[2024] SGHC 10", "official_url": "https://www.elitigation.sg/gd/s/2024_SGHC_10"}],
                "matched_terms": ["legitimate proprietary interest"],
                "suggested_propositions": ["legitimate_proprietary_interest"],
            },
            "authority": authority.model_dump(mode="json"),
            "case_map": approved_map.model_dump(mode="json"),
            "treatment_status": "not_verified",
        }
    ]
    manifest = {
        "catalogue_version": "v1",
        "status": "awaiting_legal_review",
        "generated_at": datetime.now(UTC).isoformat(),
        "build_tool_version": CATALOGUE_TOOL_VERSION,
        "source_datasets": [
            {"name": "fixture", "licence": "CC BY 4.0", "source_url": "https://example.test/source", "sha256": "b" * 64}
        ],
        "approved_authority_count": len(authorities),
        "approved_authorities_sha256": canonical_json_hash(authorities),
    }
    (directory / "approved_authorities.json").write_text(json.dumps(authorities), encoding="utf-8")
    (directory / "catalogue_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory


def test_catalogue_accepts_approved_exact_case_map_without_touching_runtime(tmp_path: Path) -> None:
    catalogue = _write_catalogue(tmp_path)
    loaded = load_catalogue(catalogue)
    assert loaded[0]["authority"]["citation"] == "[2025] SGHC 1"
    assert ActiveCorpusRepository(tmp_path / "fresh-runtime.json").list_authorities() == []


def test_catalogue_rejects_unanchored_case_map(tmp_path: Path) -> None:
    catalogue = _write_catalogue(tmp_path)
    authorities = json.loads((catalogue / "approved_authorities.json").read_text(encoding="utf-8"))
    authorities[0]["case_map"]["annotations"][0]["supporting_quote"] = "Invented quotation"
    (catalogue / "approved_authorities.json").write_text(json.dumps(authorities), encoding="utf-8")
    manifest = json.loads((catalogue / "catalogue_manifest.json").read_text(encoding="utf-8"))
    manifest["approved_authorities_sha256"] = canonical_json_hash(authorities)
    (catalogue / "catalogue_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CatalogueValidationError, match="anchor validation"):
        load_catalogue(catalogue)


def test_ready_catalogue_requires_exactly_twenty_five_reviewed_authorities(tmp_path: Path) -> None:
    catalogue = _write_catalogue(tmp_path)
    manifest = json.loads((catalogue / "catalogue_manifest.json").read_text(encoding="utf-8"))
    manifest["status"] = "ready"
    (catalogue / "catalogue_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CatalogueValidationError, match="exactly 25"):
        load_catalogue(catalogue, require_ready=True)


def test_shortlist_streams_latin1_metadata_without_emitting_citation_paragraphs(tmp_path: Path) -> None:
    dataset = tmp_path / "sg-legalcite.csv"
    fields = [
        "Judgment_URL",
        "Judgment_Reference",
        "Case Name",
        "Key Principles Illustrated",
        "Issue",
        "Issue Group",
        "Cited Case",
        "Paragraph",
    ]
    rows = [
        {
            "Judgment_URL": "https://www.elitigation.sg/gd/s/2024_SGHC_1",
            "Judgment_Reference": "[2024] SGHC 1",
            "Case Name": "First Citing Judgment [2024] SGHC 1",
            "Key Principles Illustrated": "Legitimate proprietary interest in a restrictive covenant",
            "Issue": "Employment restraint",
            "Issue Group": "Employment",
            "Cited Case": "Example Candidate [2020] SGCA 1",
            "Paragraph": "Raw nearby discussion must never be emitted.",
        },
        {
            "Judgment_URL": "https://www.elitigation.sg/gd/s/2025_SGHC_2",
            "Judgment_Reference": "[2025] SGHC 2",
            "Case Name": "Second Citing Judgment [2025] SGHC 2",
            "Key Principles Illustrated": "Customer connection",
            "Issue": "Restrictive covenant",
            "Issue Group": "Employment",
            "Cited Case": "Example Candidate [2020] SGCA 1",
            "Paragraph": "Another raw paragraph.",
        },
        {
            "Judgment_URL": "https://www.elitigation.sg/gd/s/2025_SGHC_3",
            "Judgment_Reference": "[2025] SGHC 3",
            "Case Name": "Third Citing Judgment [2025] SGHC 3",
            "Key Principles Illustrated": "Restrictive covenant",
            "Issue": "Employment restraint",
            "Issue Group": "Employment",
            "Cited Case": "Foreign Candidate [1916] AC 688",
            "Paragraph": "Foreign authority is not a Singapore catalogue lead.",
        },
        {
            "Judgment_URL": "https://www.elitigation.sg/gd/s/2020_SGCA_1",
            "Judgment_Reference": "[2020] SGCA 1",
            "Case Name": "Example Candidate [2020] SGCA 1",
            "Key Principles Illustrated": "",
            "Issue": "",
            "Issue Group": "",
            "Cited Case": "",
            "Paragraph": "",
        },
    ]
    with dataset.open("w", encoding="latin-1", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    shortlist = build_shortlist(dataset, limit=5, chunk_size=1)
    assert shortlist["candidates"][0]["candidate_name"] == "Example Candidate [2020] SGCA 1"
    assert shortlist["candidates"][0]["candidate_citation"] == "[2020] SGCA 1"
    assert shortlist["candidates"][0]["match_count"] == 2
    assert len(shortlist["candidates"]) == 1
    assert "Paragraph" not in json.dumps(shortlist)
    assert "Raw nearby discussion" not in json.dumps(shortlist)
