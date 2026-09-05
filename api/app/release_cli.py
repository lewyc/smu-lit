"""Evaluate the ProofMark Tier 0 release gates.

The checker is deliberately fail-closed: missing legal, source, connected
audit, RLS, or rehearsal evidence is reported as pending/blocked and can never
be inferred from benchmark fixtures.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.corpus import GoldFixtureCorpusRepository
from app.snapshot_cli import SnapshotValidationError, validate_snapshot

RELEASE = "tier0-v1-citation-integrity"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _snapshot_gate(snapshot: Path, archive_root: Path, refresh_attempt: Path | None = None) -> dict[str, object]:
    if not snapshot.exists():
        attempt = _read_json(refresh_attempt) if refresh_attempt else None
        reason = f"Missing certified snapshot: {snapshot}"
        if attempt and attempt.get("status") == "fallback":
            reason = f"{reason}; latest official refresh fell back: {attempt.get('fallback_reason', 'source unavailable')}"
        return {"status": "blocked", "reason": reason}
    try:
        summary = validate_snapshot(snapshot, require_certified=True)
    except SnapshotValidationError as exc:
        return {"status": "blocked", "reason": str(exc)}
    target_keys = {item.citation_key for item in GoldFixtureCorpusRepository().list_authorities()}
    payload = _read_json(snapshot)
    actual_keys = {str(item.get("citation_key")) for item in (payload or {}).get("authorities", []) if isinstance(item, dict)}
    if actual_keys != target_keys:
        return {
            "status": "blocked",
            "reason": "Snapshot must contain exactly the six Tier 0 target authorities.",
            "missing_targets": sorted(target_keys - actual_keys),
            "unexpected_targets": sorted(actual_keys - target_keys),
        }
    version = str(summary["snapshot_version"])
    archive = archive_root / version
    manifest = _read_json(archive / "manifest.json")
    if not (archive / "frozen_snapshot.json").exists() or not manifest or manifest.get("source_status") != "certified_official_snapshot":
        return {"status": "blocked", "reason": f"Certified archive is missing or incomplete for snapshot {version}."}
    return {"status": "passed", "snapshot": summary, "archive": str(archive)}


def _benchmark_gate(path: Path) -> dict[str, object]:
    payload = _read_json(path)
    if not payload or payload.get("release") != RELEASE:
        return {"status": "blocked", "reason": f"Missing or invalid benchmark evidence: {path}"}
    benchmark = payload.get("benchmark") or {}
    release_gate = payload.get("release_gate") or {}
    if not all(release_gate.values()) or benchmark.get("error_count") != 0 or benchmark.get("p95_latency_ms", 999999) >= 1500:
        return {"status": "blocked", "reason": "Benchmark release gate is not passing.", "artifact": str(path)}
    return {
        "status": "passed",
        "artifact": str(path),
        "fixture_count": benchmark.get("fixture_count"),
        "correct_count": benchmark.get("correct_count"),
        "error_count": benchmark.get("error_count"),
        "p95_latency_ms": benchmark.get("p95_latency_ms"),
    }


def _evidence_gate(path: Path, *, label: str, required: tuple[str, ...]) -> dict[str, object]:
    payload = _read_json(path)
    if not payload or payload.get("status") != "passed":
        return {"status": "pending", "reason": f"Missing passed {label} evidence: {path}"}
    missing = [key for key in required if not payload.get(key)]
    if missing:
        return {"status": "pending", "reason": f"{label} evidence is missing: {', '.join(missing)}"}
    return {"status": "passed", "artifact": str(path), **{key: payload[key] for key in required}}


def check_release(*, root: Path) -> dict[str, object]:
    evidence = root / "data" / "release_evidence" / "tier0_v1"
    snapshot_gate = _snapshot_gate(
        root / "data" / "frozen_snapshot.json",
        root / "data" / "snapshot_archive",
        evidence / "refresh_attempt.json",
    )
    legal_gate = _evidence_gate(
        evidence / "legal_review.json",
        label="legal source review",
        required=("reviewer", "authority_count", "approvals_complete", "treatment_registry_reviewed"),
    )
    if snapshot_gate.get("status") != "passed":
        legal_gate = {
            "status": "pending",
            "reason": "Legal approval can be recorded only after the official snapshot exists and validates.",
        }
    elif legal_gate.get("status") == "passed" and legal_gate.get("authority_count") != 6:
        legal_gate = {
            "status": "blocked",
            "reason": "Legal review evidence must cover exactly the six Tier 0 authorities.",
        }
    gates = {
        "official_six_authority_snapshot": snapshot_gate,
        "legal_source_review": legal_gate,
        "benchmark": _benchmark_gate(evidence / "benchmark.json"),
        "rls": _evidence_gate(
            evidence / "rls.json", label="RLS", required=("test_count", "passed_count", "environment")
        ),
        "connected_audit": _evidence_gate(
            evidence / "connected_supabase.json",
            label="connected audit",
            required=("audit_public_id", "persisted_after_reload", "tenant_scoped"),
        ),
        "offline_rehearsal": _evidence_gate(
            evidence / "offline_rehearsal" / "rehearsal.json",
            label="offline rehearsal",
            required=("network_disabled", "source_cached", "snapshot_version"),
        ),
    }
    release_ready = all(gate.get("status") == "passed" for gate in gates.values())
    return {
        "release": RELEASE,
        "release_ready": release_ready,
        "checked_at": datetime.now(UTC).isoformat(),
        "gates": gates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check ProofMark Tier 0 release evidence")
    parser.add_argument("command", nargs="?", choices=("check",), default="check")
    parser.add_argument("--api-root", type=Path, default=Path("."), help="api directory")
    parser.add_argument("--output", type=Path, default=Path("data/release_evidence/tier0_v1/release_status.json"))
    args = parser.parse_args()
    report = check_release(root=args.api_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["release_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
