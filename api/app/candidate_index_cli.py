from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.candidate_retrieval import (
    DEFAULT_CATALOGUE_DIR,
    DEFAULT_INDEX_DIR,
    CandidateIndexError,
    build_candidate_index,
)
from app.research_catalog import CatalogueValidationError


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the approved offline candidate-authority hybrid index")
    parser.add_argument("--catalogue-dir", type=Path, default=DEFAULT_CATALOGUE_DIR)
    parser.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX_DIR)
    parser.add_argument("--calibration", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = build_candidate_index(args.catalogue_dir, args.index_dir, args.calibration)
    except (CandidateIndexError, CatalogueValidationError, FileNotFoundError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
