from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings
from app.corpus import GoldFixtureCorpusRepository
from app.engine import AuditEngine


def _working_tree_id() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "uncommitted-or-unavailable"
    commit = result.stdout.strip() or "uncommitted-or-unavailable"
    return commit + ("-dirty" if dirty else "")


def run_release_benchmark(*, performance_runs: int, output: Path) -> dict[str, object]:
    if performance_runs < 250:
        raise ValueError("Tier 0 release evidence requires at least 250 performance runs")

    engine = AuditEngine(Settings(PROOFMARK_DATA_MODE="demo", GEMINI_API_KEY=""), GoldFixtureCorpusRepository())
    result = engine.benchmark(performance_runs=performance_runs)
    payload: dict[str, object] = {
        "release": "tier0-v1-citation-integrity",
        "generated_at": datetime.now(UTC).isoformat(),
        "working_tree_id": _working_tree_id(),
        "benchmark": result.model_dump(mode="json"),
        "release_gate": {
            "zero_errors": result.error_count == 0,
            "fixture_pack_exact": result.correct_count == result.fixture_count,
            "p95_under_1500ms": result.p95_latency_ms < 1500,
            "gold_fixture_corpus_only": result.gold_authority_count > 0,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if not all(payload["release_gate"].values()):
        raise RuntimeError(f"Tier 0 benchmark release gate failed: {payload['release_gate']}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run and archive ProofMark Tier 0 benchmark evidence")
    parser.add_argument("--runs", type=int, default=250)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/release_evidence/tier0_v1/benchmark.json"),
    )
    args = parser.parse_args()
    payload = run_release_benchmark(performance_runs=args.runs, output=args.output)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
