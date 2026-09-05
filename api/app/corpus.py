from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Protocol

from app.models import Authority, CorpusMetadata, CoverageCell, Passage

GOLD_CORPUS_VERSION = "sg-employment-restraints-gold-fixtures.1"
EMPTY_CORPUS_VERSION = "sg-employment-restraints-auto-empty.1"
TOPIC_PROFILE_VERSION = "sg-employment-restraints-topic.1"
SCOPE = (
    "Singapore employment restraint-of-trade judgments discovered from the official "
    "SG Courts/eLitigation source. This is an evaluation corpus, not legal advice or "
    "a comprehensive case-law database."
)
SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "frozen_snapshot.json"

# These short, hand-labelled extracts are deliberately isolated to the benchmark.
# They never become runtime evidence for an ordinary user audit.
AUTHORITIES = [
    Authority(
        id="man-financial-2007",
        citation="[2007] SGCA 53",
        citation_key="2007SGCA53",
        case_name="Man Financial (S) Pte Ltd v Wong Bark Chuan David",
        court="Court of Appeal",
        decision_date="2007-11-30",
        official_url="https://www.elitigation.sg/gdviewer/s/2007_SGCA_53",
        source_status="gold_fixture",
        source_provenance="gold_fixture",
        assessment_status="gold_fixture",
        passages=[
            Passage(
                id="man-70",
                paragraph_label="[70]",
                text="A restraint must protect a legitimate proprietary interest before its reasonableness is considered.",
                supported_propositions=["legitimate_proprietary_interest"],
                limitations=["Two-stage inquiry; enforceability remains fact-sensitive."],
            ),
            Passage(
                id="man-74",
                paragraph_label="[74]",
                text="Reasonableness is assessed both between the contracting parties and with reference to the public interest.",
                supported_propositions=["reasonableness_between_parties", "reasonableness_public_interest"],
                limitations=["No single factor determines reasonableness."],
            ),
        ],
    ),
    Authority(
        id="claas-2010",
        citation="[2010] SGCA 3",
        citation_key="2010SGCA3",
        case_name="CLAAS Medical Centre Pte Ltd v Ng Boon Ching",
        court="Court of Appeal",
        decision_date="2010-01-28",
        official_url="https://www.elitigation.sg/gd/s/2010_SGCA_3",
        source_status="gold_fixture",
        source_provenance="gold_fixture",
        assessment_status="gold_fixture",
        passages=[
            Passage(
                id="claas-59",
                paragraph_label="[59]-[60]",
                text=(
                    "A Singapore-wide geographic restraint was not unreasonable on the "
                    "particular evidence concerning the clinic's patient goodwill."
                ),
                supported_propositions=["geographic_scope", "customer_connections"],
                limitations=[
                    "Conclusion depended on the nature and geographic reach of the goodwill.",
                    "It does not establish that every Singapore-wide restraint is reasonable.",
                ],
            ),
            Passage(
                id="claas-61",
                paragraph_label="[61]",
                text="Reasonableness is assessed in the circumstances existing when the parties entered the covenant.",
                supported_propositions=["reasonableness_between_parties", "duration_scope"],
                limitations=["Duration remains fact-sensitive."],
            ),
        ],
    ),
    Authority(
        id="ht-srl-2019",
        citation="[2019] SGHC 96",
        citation_key="2019SGHC96",
        case_name="HT SRL v Wee Shuo Woon",
        court="High Court",
        decision_date="2019-04-16",
        official_url="https://www.elitigation.sg/gdviewer/s/2019_SGHC_96",
        source_status="gold_fixture",
        source_provenance="gold_fixture",
        assessment_status="gold_fixture",
        passages=[
            Passage(
                id="ht-82",
                paragraph_label="[82]-[84]",
                text=(
                    "The activity prohibition, lack of geographic limit, and one-year "
                    "duration were assessed together and found unreasonable on those facts."
                ),
                supported_propositions=["activity_scope", "geographic_scope", "duration_scope"],
                limitations=[
                    "Fact-specific result; it is not an automatic rule for all worldwide restraints.",
                    "The clause's combined breadth mattered.",
                ],
            )
        ],
    ),
    Authority(
        id="shopee-2024",
        citation="[2024] SGHC 29",
        citation_key="2024SGHC29",
        case_name="Shopee Singapore Pte Ltd v Lim Teck Yong",
        court="High Court",
        decision_date="2024-02-01",
        official_url="https://www.elitigation.sg/gdviewer/s/2024_SGHC_29",
        source_status="gold_fixture",
        source_provenance="gold_fixture",
        assessment_status="gold_fixture",
        passages=[
            Passage(
                id="shopee-18",
                paragraph_label="[18]",
                text=(
                    "Employment restraint clauses are prima facie void and unenforceable "
                    "unless the restraint-of-trade requirements are satisfied."
                ),
                supported_propositions=["prima_facie_unenforceable"],
                limitations=["Prima facie is not the same as automatically or invariably void."],
            ),
            Passage(
                id="shopee-27",
                paragraph_label="[27]-[29]",
                text="Recognised interests may include trade secrets, trade connections, and maintaining a stable and trained workforce.",
                supported_propositions=[
                    "confidential_information",
                    "customer_connections",
                    "stable_trained_workforce",
                    "legitimate_proprietary_interest",
                ],
                limitations=["The asserted interest must exist on the facts and fit the clause."],
            ),
        ],
    ),
]

NEGATIVE_CITATION_CHECKS = {
    "2099SGCA999": {
        "exists": False,
        "official_source": "https://www.elitigation.sg/gd/",
        "checker": "ProofMark adversarial-fixture curator",
        "checked_at": "2026-09-05T00:00:00+08:00",
        "note": "Future-dated adversarial fixture. Re-run an official registry search before external use.",
    }
}

DEMO_ANSWER = """Singapore employment restraints are prima facie unenforceable unless the employer justifies them [2024] SGHC 29 at [18].
An employer must identify a legitimate proprietary interest before reasonableness is considered [2007] SGCA 53 at [70].
All worldwide one-year non-competes are automatically void under [2019] SGHC 96 at [82].
CLAAS proves that every Singapore-wide restraint is always unreasonable [2010] SGCA 3 at [59].
Any former employee who contacts a customer necessarily misuses confidential information.
The Court of Appeal created a mandatory two-year restraint in [2099] SGCA 999.
Separately, the PDPA always permits employers to publish former employees' personal data."""


class CorpusRepository(Protocol):
    def get_metadata(self) -> CorpusMetadata: ...

    def list_authorities(self) -> list[Authority]: ...

    def resolve(self, citation_key: str) -> Authority | None: ...

    def negative_check(self, citation_key: str) -> dict[str, object] | None: ...


def _coverage(authorities: list[Authority]) -> list[CoverageCell]:
    buckets: dict[tuple[str, str, str, str], int] = {}
    for authority in authorities:
        year_band = f"{authority.decision_date.year // 5 * 5}-{authority.decision_date.year // 5 * 5 + 4}"
        for passage in authority.passages:
            for proposition in passage.supported_propositions:
                key = (authority.court, year_band, proposition, passage.outcome_direction)
                buckets[key] = buckets.get(key, 0) + 1
    return [
        CoverageCell(
            court=court,
            decision_year_band=year_band,
            proposition=proposition,
            outcome_direction=direction,
            passage_count=count,
        )
        for (court, year_band, proposition, direction), count in sorted(buckets.items())
    ]


def _metadata(
    version: str,
    authorities: list[Authority],
    *,
    source_status: str,
    profile_version: str | None,
    snapshot_created_at: datetime | None,
    is_cached: bool,
) -> CorpusMetadata:
    payload = json.dumps([authority.model_dump(mode="json") for authority in authorities], sort_keys=True)
    return CorpusMetadata(
        version=version,
        name="Singapore employment restraints automated snapshot",
        jurisdiction="Singapore",
        scope_statement=SCOPE,
        content_hash=hashlib.sha256(payload.encode()).hexdigest(),
        source_status=source_status,
        limitations=[
            "Only numbered paragraphs retrieved from validated SG Courts/eLitigation judgment URLs are included.",
            "AI annotations select exact stored paragraphs; they are not legal conclusions.",
            "Machine-discovered positive evidence always requires lawyer context review.",
            "Absence from the snapshot is never proof a citation is fabricated.",
        ],
        snapshot_created_at=snapshot_created_at,
        authority_count=len(authorities),
        passage_count=sum(len(authority.passages) for authority in authorities),
        profile_version=profile_version,
        is_cached=is_cached,
        coverage=_coverage(authorities),
    )


class GoldFixtureCorpusRepository:
    def __init__(self) -> None:
        self._authorities = {item.citation_key: item for item in AUTHORITIES}

    def get_metadata(self) -> CorpusMetadata:
        return _metadata(
            GOLD_CORPUS_VERSION,
            AUTHORITIES,
            source_status="gold_fixture",
            profile_version=None,
            snapshot_created_at=None,
            is_cached=False,
        )

    def list_authorities(self) -> list[Authority]:
        return AUTHORITIES

    def resolve(self, citation_key: str) -> Authority | None:
        return self._authorities.get(citation_key)

    def negative_check(self, citation_key: str) -> dict[str, object] | None:
        return NEGATIVE_CITATION_CHECKS.get(citation_key)


class ActiveCorpusRepository:
    """Thread-safe active snapshot used by normal audits; it never performs network work."""

    def __init__(self, snapshot_path: Path = SNAPSHOT_PATH) -> None:
        self.snapshot_path = snapshot_path
        self._lock = RLock()
        self._authorities: dict[str, Authority] = {}
        self._metadata = _metadata(
            EMPTY_CORPUS_VERSION,
            [],
            source_status="unavailable",
            profile_version=TOPIC_PROFILE_VERSION,
            snapshot_created_at=None,
            is_cached=False,
        )
        self._load_cached_snapshot()

    def _load_cached_snapshot(self) -> None:
        if not self.snapshot_path.exists():
            return
        try:
            payload = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
            metadata = CorpusMetadata.model_validate(payload["metadata"])
            authorities = [Authority.model_validate(item) for item in payload["authorities"]]
        except (OSError, ValueError, KeyError):
            return
        metadata.is_cached = True
        self._metadata = metadata
        self._authorities = {item.citation_key: item for item in authorities}

    def activate(
        self,
        authorities: list[Authority],
        *,
        profile_version: str = TOPIC_PROFILE_VERSION,
        persist_snapshot: bool = True,
    ) -> CorpusMetadata:
        if not authorities:
            raise ValueError("A corpus snapshot must contain at least one accepted authority")
        now = datetime.now(UTC)
        version = f"sg-employment-restraints-auto-{now:%Y.%m.%d.%H%M%S}"
        metadata = _metadata(
            version,
            authorities,
            source_status="officially_sourced",
            profile_version=profile_version,
            snapshot_created_at=now,
            is_cached=False,
        )
        with self._lock:
            self._authorities = {item.citation_key: item for item in authorities}
            self._metadata = metadata
            if persist_snapshot:
                self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
                self.snapshot_path.write_text(
                    json.dumps(
                        {
                            "metadata": metadata.model_dump(mode="json"),
                            "authorities": [item.model_dump(mode="json") for item in authorities],
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
        return metadata

    def get_metadata(self) -> CorpusMetadata:
        with self._lock:
            return self._metadata.model_copy(deep=True)

    def list_authorities(self) -> list[Authority]:
        with self._lock:
            return [item.model_copy(deep=True) for item in self._authorities.values()]

    def resolve(self, citation_key: str) -> Authority | None:
        with self._lock:
            item = self._authorities.get(citation_key)
            return item.model_copy(deep=True) if item else None

    def negative_check(self, citation_key: str) -> dict[str, object] | None:
        return NEGATIVE_CITATION_CHECKS.get(citation_key)


# Kept as a compatibility name for small integration points. Runtime code should
# use ActiveCorpusRepository; benchmark code should use GoldFixtureCorpusRepository.
LocalCorpusRepository = ActiveCorpusRepository
