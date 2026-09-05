import json
from pathlib import Path

from app.release_cli import check_release


def test_release_check_fails_closed_when_external_evidence_is_missing(tmp_path: Path) -> None:
    evidence = tmp_path / "data" / "release_evidence" / "tier0_v1"
    evidence.mkdir(parents=True)
    (evidence / "benchmark.json").write_text(
        json.dumps(
            {
                "release": "tier0-v1-citation-integrity",
                "benchmark": {"error_count": 0, "p95_latency_ms": 1},
                "release_gate": {"zero_errors": True, "fixture_pack_exact": True},
            }
        ),
        encoding="utf-8",
    )
    report = check_release(root=tmp_path)
    assert report["release_ready"] is False
    assert report["gates"]["official_six_authority_snapshot"]["status"] == "blocked"
    assert report["gates"]["connected_audit"]["status"] == "pending"

