from __future__ import annotations

import argparse
import json

from app.config import get_settings
from app.corpus import AUTHORITIES, ActiveCorpusRepository
from app.refresh import CorpusRefreshService, SGCourtsConnector, SourceCandidate, TopicProfile, new_refresh_run


class Tier0TargetConnector:
    """Fetch the six release authorities through the official connector only."""

    def __init__(self, delegate: SGCourtsConnector) -> None:
        self.delegate = delegate

    def discover(self, profile: TopicProfile, limit: int) -> list[SourceCandidate]:
        return [
            SourceCandidate(
                citation=authority.citation,
                citation_key=authority.citation_key,
                url=authority.official_url,
                discovery_query="tier0-gold-target-pack",
            )
            for authority in AUTHORITIES[:limit]
        ]

    def fetch(self, candidate: SourceCandidate) -> str:
        # A targeted release refresh still obeys robots guidance and the
        # allowlisted official connector; it never reads fixture passage text.
        self.delegate._ensure_robots_allow_refresh()
        return self.delegate.fetch(candidate)


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh the ProofMark official corpus")
    parser.add_argument(
        "--tier0-target-pack",
        action="store_true",
        help="fetch exactly the six release authorities through official URLs",
    )
    args = parser.parse_args()
    settings = get_settings()
    connector = Tier0TargetConnector(SGCourtsConnector()) if args.tier0_target_pack else None
    result = CorpusRefreshService(ActiveCorpusRepository(), settings, connector=connector).refresh(new_refresh_run())
    print(json.dumps(result.model_dump(mode="json"), indent=2))
    return 0 if result.status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
