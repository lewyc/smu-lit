from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from app.models import Authority, CorpusMetadata


class SnapshotValidationError(ValueError):
    pass


def _load_snapshot(path: Path) -> tuple[CorpusMetadata, list[Authority], bytes]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
        metadata = CorpusMetadata.model_validate(payload["metadata"])
        authorities = [Authority.model_validate(item) for item in payload["authorities"]]
    except (OSError, KeyError, ValueError) as exc:
        raise SnapshotValidationError(f"invalid snapshot: {exc}") from exc
    if not authorities:
        raise SnapshotValidationError("snapshot contains no authorities")
    return metadata, authorities, raw


def validate_snapshot(path: Path, *, require_certified: bool = False) -> dict[str, object]:
    metadata, authorities, raw = _load_snapshot(path)
    if metadata.authority_count != len(authorities):
        raise SnapshotValidationError("metadata authority count does not match snapshot contents")
    if metadata.passage_count != sum(len(item.passages) for item in authorities):
        raise SnapshotValidationError("metadata passage count does not match snapshot contents")
    expected_content_hash = hashlib.sha256(
        json.dumps([authority.model_dump(mode="json") for authority in authorities], sort_keys=True).encode("utf-8")
    ).hexdigest()
    if metadata.content_hash != expected_content_hash:
        raise SnapshotValidationError("metadata content hash does not match snapshot contents")
    for authority in authorities:
        host = urlparse(authority.official_url).hostname or ""
        if host not in {"www.elitigation.sg", "elitigation.sg"}:
            raise SnapshotValidationError(f"{authority.citation}: official URL is not an eLitigation URL")
        if not re.fullmatch(r"\[\d{4}\] SG[A-Z()]+ \d+", authority.citation):
            raise SnapshotValidationError(f"{authority.citation}: malformed neutral citation")
        if not authority.case_name.strip() or not authority.court.strip():
            raise SnapshotValidationError(f"{authority.citation}: missing canonical case identity metadata")
        if authority.source_provenance != "officially_sourced":
            raise SnapshotValidationError(f"{authority.citation}: snapshot evidence is not officially sourced")
        if not authority.document_hash or not re.fullmatch(r"[0-9a-f]{64}", authority.document_hash):
            raise SnapshotValidationError(f"{authority.citation}: missing SHA-256 document hash")
        if require_certified and (
            authority.source_review_status != "approved" or not authority.source_reviewer or not authority.source_reviewed_at
        ):
            raise SnapshotValidationError(f"{authority.citation}: missing approved source-review metadata")
        for passage in authority.passages:
            if not re.search(r"\[\d+", passage.paragraph_label):
                raise SnapshotValidationError(f"{authority.citation}: passage lacks a numbered paragraph label")
            if require_certified:
                if passage.assessment_status != "human_reviewed":
                    raise SnapshotValidationError(f"{authority.citation} {passage.paragraph_label}: evidence is not human reviewed")
                if not passage.source_role_reviewed or passage.source_role == "unreviewed" or not passage.source_role_reviewer:
                    raise SnapshotValidationError(f"{authority.citation} {passage.paragraph_label}: source role is not reviewed")
    return {
        "snapshot_version": metadata.version,
        "content_hash": metadata.content_hash,
        "file_hash": hashlib.sha256(raw).hexdigest(),
        "authority_count": len(authorities),
        "passage_count": sum(len(item.passages) for item in authorities),
        "certified": require_certified,
    }


def archive_snapshot(snapshot: Path, archive_root: Path, *, require_certified: bool) -> Path:
    summary = validate_snapshot(snapshot, require_certified=require_certified)
    destination = archive_root / str(summary["snapshot_version"])
    if destination.exists():
        raise SnapshotValidationError(f"archive already exists: {destination}")
    destination.mkdir(parents=True)
    try:
        shutil.copyfile(snapshot, destination / "frozen_snapshot.json")
        manifest = {
            **summary,
            "archived_at": datetime.now(UTC).isoformat(),
            "source_status": "certified_official_snapshot" if require_certified else "official_snapshot_pending_review",
        }
        (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate or archive a ProofMark frozen snapshot")
    parser.add_argument("command", choices=("validate", "archive"))
    parser.add_argument("--snapshot", type=Path, default=Path("data/frozen_snapshot.json"))
    parser.add_argument("--archive-root", type=Path, default=Path("data/snapshot_archive"))
    parser.add_argument("--require-certified", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "validate":
            print(json.dumps(validate_snapshot(args.snapshot, require_certified=args.require_certified), indent=2))
        else:
            print(archive_snapshot(args.snapshot, args.archive_root, require_certified=args.require_certified))
    except SnapshotValidationError as exc:
        print(f"snapshot validation failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
