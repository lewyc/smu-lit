import hashlib
import json
from pathlib import Path

import pytest

from app.corpus import ActiveCorpusRepository
from app.models import Authority, Passage
from app.snapshot_cli import SnapshotValidationError, archive_snapshot, validate_snapshot


def _snapshot(path: Path) -> Path:
    corpus = ActiveCorpusRepository(path)
    corpus.activate(
        [
            Authority(
                id="certified-example",
                citation="[2025] SGHC 101",
                citation_key="2025SGHC101",
                case_name="Example Employer Pte Ltd v Example Employee",
                court="High Court",
                decision_date="2025-01-01",
                official_url="https://www.elitigation.sg/gd/s/2025_SGHC_101",
                source_status="officially_sourced",
                source_provenance="officially_sourced",
                assessment_status="human_reviewed",
                document_hash="a" * 64,
                source_review_status="approved",
                source_reviewer="legal-reviewer",
                source_reviewed_at="2026-09-06T00:00:00Z",
                passages=[
                    Passage(
                        id="example-1",
                        paragraph_label="[1]",
                        text="A legitimate proprietary interest is required.",
                        supported_propositions=["legitimate_proprietary_interest"],
                        source_provenance="officially_sourced",
                        assessment_status="human_reviewed",
                        source_role="judicial_holding",
                        source_role_reviewed=True,
                        source_role_reviewer="legal-reviewer",
                    )
                ],
            )
        ]
    )
    return path


def test_certified_snapshot_validates_and_archives(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path / "frozen_snapshot.json")
    summary = validate_snapshot(snapshot, require_certified=True)
    assert summary["certified"] is True
    archive = archive_snapshot(snapshot, tmp_path / "archive", require_certified=True)
    assert (archive / "frozen_snapshot.json").exists()
    assert json.loads((archive / "manifest.json").read_text(encoding="utf-8"))["source_status"] == "certified_official_snapshot"


def test_certified_snapshot_rejects_missing_hash_or_role_review(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path / "frozen_snapshot.json")
    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    payload["authorities"][0]["document_hash"] = None
    payload["metadata"]["content_hash"] = hashlib.sha256(
        json.dumps(payload["authorities"], sort_keys=True).encode("utf-8")
    ).hexdigest()
    snapshot.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SnapshotValidationError, match="document hash"):
        validate_snapshot(snapshot, require_certified=True)
