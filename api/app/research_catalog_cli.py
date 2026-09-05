from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.research_catalog import CatalogueValidationError, build_shortlist, load_catalogue


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="ProofMark offline research catalogue tooling")
    commands = parser.add_subparsers(dest="command", required=True)
    shortlist = commands.add_parser("shortlist", help="stream SG-LegalCite into metadata-only research leads")
    shortlist.add_argument("--dataset", type=Path, required=True)
    shortlist.add_argument("--output", type=Path, required=True)
    shortlist.add_argument("--limit", type=int, default=100)
    shortlist.add_argument("--chunk-size", type=int, default=5_000)
    validate = commands.add_parser("validate", help="validate a versioned approved research catalogue")
    validate.add_argument("--catalogue-dir", type=Path, required=True)
    validate.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "shortlist":
            payload = build_shortlist(args.dataset, limit=args.limit, chunk_size=args.chunk_size)
            _write_json(args.output, payload)
            print(f"Wrote {len(payload['candidates'])} research-only candidates to {args.output}")
        else:
            records = load_catalogue(args.catalogue_dir, require_ready=args.require_ready)
            print(f"Validated {len(records)} approved catalogue authorities in {args.catalogue_dir}")
    except (CatalogueValidationError, OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
