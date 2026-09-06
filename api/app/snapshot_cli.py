from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from app.snapshot_validation import SnapshotValidationError, load_snapshot, validate_snapshot_records


def validate_snapshot(path: Path, *, require_certified: bool = False) -> dict[str, object]:
    metadata, authorities, raw = load_snapshot(path)
    validate_snapshot_records(metadata, authorities, require_certified=require_certified)
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
