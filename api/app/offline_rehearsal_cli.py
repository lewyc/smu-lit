"""Run the Tier 0 demo path without network access.

This command intentionally refuses to use the gold fixture repository.  It
requires an archived, legally certified official snapshot so the rehearsal is
evidence of the actual release path rather than of the benchmark-only path.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings
from app.corpus import DEMO_ANSWER, ActiveCorpusRepository, GoldFixtureCorpusRepository
from app.engine import AuditEngine
from app.models import AuditSubmission
from app.snapshot_cli import SnapshotValidationError, validate_snapshot


def run_offline_rehearsal(*, snapshot: Path, output: Path, require_certified: bool = True) -> dict[str, object]:
    """Audit the prepared answer using only a validated local snapshot.

    No connector, refresh manager, Gemini client, or Supabase repository is
    constructed here.  ``network_disabled`` is recorded as an explicit claim
    about the execution mode so the resulting artifact can be reviewed later.
    """

    summary = validate_snapshot(snapshot, require_certified=require_certified)
    corpus = ActiveCorpusRepository(snapshot)
    metadata = corpus.get_metadata()
    expected = {item.citation_key for item in GoldFixtureCorpusRepository().list_authorities()}
    actual = {item.citation_key for item in corpus.list_authorities()}
    missing = sorted(expected - actual)
    if missing:
        raise SnapshotValidationError(
            "certified release snapshot is missing Tier 0 target authorities: " + ", ".join(missing)
        )
    settings = Settings(PROOFMARK_DATA_MODE="demo", GEMINI_API_KEY="")
    result = AuditEngine(settings, corpus).audit(
        AuditSubmission(answer=DEMO_ANSWER, audit_mode="citation_only", parser_mode="local", reuse_cache=False)
    )
    if result.audit_mode != "citation_only" or result.parser_used != "local":
        raise RuntimeError("offline rehearsal did not use the deterministic citation-only parser")
    if not metadata.is_cached:
        raise RuntimeError("offline rehearsal did not load the snapshot as a cached source")
    if any(claim.verdict == "verified" for claim in result.claims):
        raise RuntimeError("ordinary runtime snapshot produced a benchmark-only verified verdict")

    payload: dict[str, object] = {
        "release": "tier0-v1-citation-integrity",
        "status": "passed",
        "network_disabled": True,
        "generated_at": datetime.now(UTC).isoformat(),
        "snapshot": summary,
        "snapshot_version": metadata.version,
        "source_cached": metadata.is_cached,
        "engine_version": result.engine_version,
        "parser_used": result.parser_used,
        "claim_count": len(result.claims),
        "summary_counts": result.summary_counts,
        "claims": [
            {
                "order": claim.order,
                "verdict": claim.verdict,
                "citation": claim.citation,
                "citation_identity_status": claim.citation_identity_status,
                "pinpoint_status": claim.pinpoint_status,
                "quote_status": claim.quote_status,
                "source_role_status": claim.source_role_status,
                "currency_status": claim.currency_status,
                "official_url": claim.evidence[0].official_url if claim.evidence else None,
            }
            for claim in result.claims
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the offline Tier 0 rehearsal against a certified snapshot")
    parser.add_argument("--snapshot", type=Path, default=Path("data/frozen_snapshot.json"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/release_evidence/tier0_v1/offline_rehearsal/rehearsal.json"),
    )
    parser.add_argument("--allow-uncertified", action="store_true", help="diagnostic only; not valid release evidence")
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                run_offline_rehearsal(
                    snapshot=args.snapshot,
                    output=args.output,
                    require_certified=not args.allow_uncertified,
                ),
                indent=2,
            )
        )
    except (SnapshotValidationError, RuntimeError, OSError, ValueError) as exc:
        print(f"offline rehearsal blocked: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
