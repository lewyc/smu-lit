from pathlib import Path

from app.config import Settings
from app.corpus import (
    AUTHORITIES,
    ActiveCorpusRepository,
    GoldFixtureCorpusRepository,
)
from app.engine import AuditEngine
from app.models import AuditSubmission, Authority, Passage
from app.parsers import LocalClaimParser, normalise_citation


def gold_engine() -> AuditEngine:
    return AuditEngine(
        Settings(PROOFMARK_DATA_MODE="demo"),
        GoldFixtureCorpusRepository(),
    )


def automated_engine(snapshot_path: Path) -> AuditEngine:
    corpus = ActiveCorpusRepository(snapshot_path)
    corpus.activate(
        [
            Authority(
                id="shopee-source-locked",
                citation="[2024] SGHC 29",
                citation_key="2024SGHC29",
                case_name="Shopee Singapore Pte Ltd v Lim Teck Yong",
                court="Singapore HC",
                decision_date="2024-02-01",
                official_url="https://www.elitigation.sg/gd/s/2024_SGHC_29",
                source_status="officially_sourced",
                source_provenance="officially_sourced",
                assessment_status="ai_supported",
                document_hash="a" * 64,
                passages=[
                    Passage(
                        id="shopee-source-59",
                        paragraph_label="[59]",
                        text=(
                            "must always – and this is a fundamental legal proposition in this "
                            "particular area of the law – be a legitimate proprietary interest"
                        ),
                        supported_propositions=["legitimate_proprietary_interest"],
                        source_provenance="officially_sourced",
                        assessment_status="ai_supported",
                        annotation_confidence=0.9,
                    )
                ],
            )
        ]
    )
    return AuditEngine(Settings(PROOFMARK_DATA_MODE="demo"), corpus)


def test_neutral_citation_normalisation_is_tolerant() -> None:
    assert normalise_citation("[2024]   sghc   29") == "2024SGHC29"
    assert normalise_citation("[2007] SGCA 53") == "2007SGCA53"


def test_local_parser_extracts_multiple_claims_and_pinpoints() -> None:
    text = (
        "A restraint is prima facie unenforceable [2024] SGHC 29 at [18].\nAll non-competes are automatically void [2019] SGHC 96 at [82]."
    )
    claims = LocalClaimParser().parse(text)
    assert len(claims) == 2
    assert claims[0].citation == "[2024] SGHC 29"
    assert claims[0].pinpoint == "[18]"
    assert claims[1].overgeneralisation_terms == ["automatically", "all non-competes"]


def test_local_parser_extracts_only_bounded_double_quoted_text() -> None:
    claim = LocalClaimParser().parse('The court said "A legitimate interest is required" [2007] SGCA 53 at [79].')[0]
    assert claim.quoted_text == "A legitimate interest is required"


def test_all_gold_authorities_resolve_exactly() -> None:
    corpus = GoldFixtureCorpusRepository()
    assert all(corpus.resolve(authority.citation_key) for authority in AUTHORITIES)


def test_gold_fixture_pack_exercises_expected_verdicts() -> None:
    engine = gold_engine()
    answers = [
        ("Employment restraints are prima facie unenforceable [2024] SGHC 29.", "verified"),
        ("A legitimate interest is required [2007] SGCA 53.", "verified"),
        ("All worldwide restraints are automatically void [2019] SGHC 96.", "context_review"),
        ("Singapore-wide restraints are always unreasonable [2010] SGCA 3.", "context_review"),
        ("Confidential information is always misused.", "unsupported"),
        ("The PDPA permits publication of personal data.", "out_of_scope"),
    ]
    assert [engine.audit(AuditSubmission(answer=text, parser_mode="local")).claims[0].verdict for text, _ in answers] == [
        expected for _, expected in answers
    ]


def test_automatically_sourced_evidence_can_never_be_verified(tmp_path: Path) -> None:
    audit = automated_engine(tmp_path / "snapshot.json").audit(
        AuditSubmission(
            answer="A legitimate interest is required [2024] SGHC 29.",
            parser_mode="local",
        )
    )
    claim = audit.claims[0]
    assert claim.verdict == "context_review"
    assert claim.evidence[0].officially_sourced
    assert claim.evidence[0].ai_supported


def test_unknown_citation_is_not_called_fabricated_without_negative_check() -> None:
    audit = gold_engine().audit(AuditSubmission(answer="A restraint is invalid [2026] SGHC 49.", parser_mode="local"))
    assert audit.claims[0].verdict == "unverified"


def test_quote_check_fails_loudly_when_the_retained_snapshot_lacks_the_pinpoint() -> None:
    audit = gold_engine().audit(
        AuditSubmission(
            answer='"Invented words" [2007] SGCA 53 at [79] establish a legitimate proprietary interest.',
            parser_mode="local",
        )
    )
    claim = audit.claims[0]
    assert (claim.verdict, claim.quote_status, claim.decision_rule_id) == ("unsupported", "unresolved", "PM-CIT-008")


def test_gemini_absence_falls_back_without_changing_gold_fixture_verdicts() -> None:
    audit = AuditEngine(
        Settings(PROOFMARK_DATA_MODE="demo", GEMINI_API_KEY="", OPENROUTER_API_KEY=""),
        GoldFixtureCorpusRepository(),
    ).audit(
        AuditSubmission(
            answer="A legitimate interest is required [2007] SGCA 53.",
            parser_mode="auto",
        )
    )
    assert audit.parser_used == "local"
    assert "not configured" in (audit.parser_fallback_reason or "")
    assert audit.claims[0].verdict == "verified"


def test_cache_key_includes_active_corpus_version(tmp_path: Path) -> None:
    submission = AuditSubmission(
        answer="A legitimate interest is required [2007] SGCA 53.",
        parser_mode="local",
    )
    gold = gold_engine()
    automatic = automated_engine(tmp_path / "snapshot.json")
    assert gold.request_cache_key(submission) != automatic.request_cache_key(submission)


def test_cached_and_stale_results_remain_traceable(tmp_path: Path) -> None:
    submission = AuditSubmission(
        answer="A legitimate interest is required [2007] SGCA 53.",
        parser_mode="local",
    )
    original = gold_engine().audit(submission)
    cached = gold_engine().cache_hit(original)
    assert cached.public_id != original.public_id
    assert cached.cache_status == "hit"
    assert cached.audit_cache_key == original.audit_cache_key
    assert cached.source_label == "Source-versioned cached audit result"

    stale = automated_engine(tmp_path / "snapshot.json").apply_freshness(original)
    assert stale.is_stale
    assert stale.active_corpus_version != stale.corpus_version


def test_approved_currency_context_is_traceable_and_invalidates_cache() -> None:
    submission = AuditSubmission(
        answer="A legitimate interest is required [2007] SGCA 53.",
        parser_mode="local",
    )
    engine = gold_engine()
    reviewed = engine.audit(
        submission,
        {"2007SGCA53": "current_reviewed"},
        "currency-reviewed-1",
    )
    assert reviewed.claims[0].currency_status == "current_reviewed"
    assert reviewed.metrics.relevance_currency_module and reviewed.metrics.relevance_currency_module.assessed
    assert engine.request_cache_key(submission, "currency-reviewed-1") != engine.request_cache_key(
        submission,
        "currency-reviewed-2",
    )

    limited = engine.audit(
        submission,
        {"2007SGCA53": "negative_treatment"},
        "currency-reviewed-2",
    )
    assert limited.claims[0].currency_status == "negative_treatment"
    assert limited.claims[0].verdict == "context_review"
    assert any(flag.code == "negative_treatment" for flag in limited.flags)


def test_benchmark_fixture_pack_is_exact() -> None:
    result = gold_engine().benchmark(performance_runs=3)
    assert result.fixture_accuracy == 100
    assert result.error_count == 0
