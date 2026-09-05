from __future__ import annotations

import hashlib
import json

from app.models import Authority, CorpusMetadata, Passage

CORPUS_VERSION = "sg-employment-restraints-2026.09-pilot.1"

SCOPE = (
    "Selected Singapore employment restraint-of-trade propositions. "
    "Not a comprehensive case-law database."
)

AUTHORITIES = [
    Authority(
        id="man-financial-2007",
        citation="[2007] SGCA 53",
        citation_key="2007SGCA53",
        case_name="Man Financial (S) Pte Ltd v Wong Bark Chuan David",
        court="Court of Appeal",
        decision_date="2007-11-30",
        official_url="https://www.elitigation.sg/gdviewer/s/2007_SGCA_53",
        source_status="research_verified",
        passages=[
            Passage(
                id="man-70",
                paragraph_label="[70]",
                text=(
                    "A restraint must protect a legitimate proprietary interest before "
                    "its reasonableness is considered."
                ),
                supported_propositions=["legitimate_proprietary_interest"],
                limitations=["Two-stage inquiry; enforceability remains fact-sensitive."],
            ),
            Passage(
                id="man-74",
                paragraph_label="[74]",
                text=(
                    "Reasonableness is assessed both between the contracting parties "
                    "and with reference to the public interest."
                ),
                supported_propositions=[
                    "reasonableness_between_parties",
                    "reasonableness_public_interest",
                ],
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
        source_status="research_verified",
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
                text=(
                    "Reasonableness is assessed in the circumstances existing when the "
                    "parties entered the covenant."
                ),
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
        source_status="research_verified",
        passages=[
            Passage(
                id="ht-82",
                paragraph_label="[82]-[84]",
                text=(
                    "The activity prohibition, lack of geographic limit, and one-year "
                    "duration were assessed together and found unreasonable on those facts."
                ),
                supported_propositions=[
                    "activity_scope",
                    "geographic_scope",
                    "duration_scope",
                ],
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
        source_status="research_verified",
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
                text=(
                    "Recognised interests may include trade secrets, trade connections, "
                    "and maintaining a stable and trained workforce."
                ),
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
        "note": (
            "Future-dated adversarial fixture. Re-run an official registry search "
            "before using it outside the demo."
        ),
    }
}

DEMO_ANSWER = """Singapore employment restraints are prima facie unenforceable unless the employer justifies them [2024] SGHC 29 at [18].
An employer must identify a legitimate proprietary interest before reasonableness is considered [2007] SGCA 53 at [70].
All worldwide one-year non-competes are automatically void under [2019] SGHC 96 at [82].
CLAAS proves that every Singapore-wide restraint is always unreasonable [2010] SGCA 3 at [59].
Any former employee who contacts a customer necessarily misuses confidential information.
The Court of Appeal created a mandatory two-year restraint in [2099] SGCA 999.
Separately, the PDPA always permits employers to publish former employees' personal data."""


def metadata() -> CorpusMetadata:
    payload = json.dumps(
        [authority.model_dump(mode="json") for authority in AUTHORITIES],
        sort_keys=True,
    )
    return CorpusMetadata(
        version=CORPUS_VERSION,
        name="Singapore employment restraints pilot",
        jurisdiction="Singapore",
        scope_statement=SCOPE,
        content_hash=hashlib.sha256(payload.encode()).hexdigest(),
        source_status="research_verified",
        limitations=[
            "Only four selected decisions are included.",
            "Passages are curated pilot extracts; legal-team sign-off is required before external use.",
            "No live Singapore Courts or commercial legal-database search is performed.",
            "TF-IDF ranking assists navigation and never determines legal truth.",
        ],
    )


class LocalCorpusRepository:
    def __init__(self) -> None:
        self._authorities = {item.citation_key: item for item in AUTHORITIES}

    def get_metadata(self) -> CorpusMetadata:
        return metadata()

    def list_authorities(self) -> list[Authority]:
        return AUTHORITIES

    def resolve(self, citation_key: str) -> Authority | None:
        return self._authorities.get(citation_key)

    def negative_check(self, citation_key: str) -> dict[str, object] | None:
        return NEGATIVE_CITATION_CHECKS.get(citation_key)
