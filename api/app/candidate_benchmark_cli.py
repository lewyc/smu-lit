from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.candidate_retrieval import (
    DEFAULT_CATALOGUE_DIR,
    DEFAULT_INDEX_DIR,
    CandidateAuthorityIndex,
    CandidateIndexError,
    benchmark_candidate_index,
)
from app.research_catalog import CatalogueValidationError


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure approved candidate-authority retrieval separately from verdict quality")
    parser.add_argument("--catalogue-dir", type=Path, default=DEFAULT_CATALOGUE_DIR)
    parser.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX_DIR)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/release_evidence/candidate_retrieval_v1/benchmark.json"),
    )
    args = parser.parse_args()
    try:
        index = CandidateAuthorityIndex.load(args.catalogue_dir, args.index_dir)
        calibration = json.loads(args.queries.read_text(encoding="utf-8"))
        result = benchmark_candidate_index(index, calibration)
    except (CandidateIndexError, CatalogueValidationError, FileNotFoundError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not all(result["release_gate"].values()):
        raise RuntimeError(f"Candidate retrieval release gate failed: {result['release_gate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
