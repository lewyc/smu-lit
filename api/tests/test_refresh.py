from pathlib import Path

import httpx

from app.config import Settings
from app.corpus import ActiveCorpusRepository
from app.refresh import (
    CorpusRefreshService,
    EvidenceAnnotation,
    ExtractedJudgment,
    GeminiEvidenceAnnotator,
    JudgmentExtractor,
    SGCourtsConnector,
    SourceCandidate,
    TopicProfile,
    new_refresh_run,
)

HTML = """
<html><body>
  <h1>Shopee Singapore Pte Ltd v Lim Teck Yong</h1>
  <p>[2024] SGHC 29</p>
  <p>Decision Date : 01 February 2024</p>
  <p>[59] must always – and this is a fundamental legal proposition
  in this particular area of the law – be a legitimate proprietary interest</p>
</body></html>
"""


class FixtureConnector:
    def __init__(self, candidates: list[SourceCandidate] | None = None) -> None:
        self.candidates = candidates or [
            SourceCandidate(
                citation="[2024] SGHC 29",
                citation_key="2024SGHC29",
                url="https://www.elitigation.sg/gd/s/2024_SGHC_29",
                discovery_query="employment restraint",
            )
        ]

    def discover(self, profile: TopicProfile, limit: int) -> list[SourceCandidate]:
        return self.candidates[:limit]

    def fetch(self, candidate: SourceCandidate) -> str:
        return HTML


class FixtureAnnotator:
    def annotate(self, judgment: ExtractedJudgment) -> list[EvidenceAnnotation]:
        return [
            EvidenceAnnotation(
                paragraph_label="[59]",
                proposition="legitimate_proprietary_interest",
                limitations=["Fact-sensitive."],
                outcome_direction="mixed",
                confidence=0.91,
            )
        ]


class MissingAnchorAnnotator:
    def annotate(self, judgment: ExtractedJudgment) -> list[EvidenceAnnotation]:
        return [
            EvidenceAnnotation(
                paragraph_label="[999]",
                proposition="legitimate_proprietary_interest",
                outcome_direction="mixed",
                confidence=0.91,
            )
        ]


class DiscoveryHttpClient:
    def get(self, url: str) -> httpx.Response:
        if url.endswith("/robots.txt"):
            return httpx.Response(
                200,
                text="User-agent: *\nAllow: /",
                request=httpx.Request("GET", url),
            )
        return httpx.Response(
            200,
            text=(
                '<a href="/gdviewer/s/2024_SGHC_29">Shopee [2024] SGHC 29</a>'
                '<a href="/gdviewer/s/2024_SGHC_29">Duplicate [2024] SGHC 29</a>'
                '<a href="https://example.com/gdviewer/s/2024_SGHC_29">Reject</a>'
            ),
            request=httpx.Request("GET", url),
        )


class MissingRobotsHttpClient(DiscoveryHttpClient):
    def get(self, url: str) -> httpx.Response:
        if url.endswith("/robots.txt"):
            return httpx.Response(404, request=httpx.Request("GET", url))
        return super().get(url)


def test_refresh_extracts_validated_heading_paragraphs_and_hashes(tmp_path: Path) -> None:
    corpus = ActiveCorpusRepository(tmp_path / "snapshot.json")
    result = CorpusRefreshService(
        corpus,
        Settings(),
        connector=FixtureConnector(),
        annotator=FixtureAnnotator(),
    ).refresh(new_refresh_run(limit=25))
    assert result.status == "complete"
    assert result.accepted_documents == 1
    authority = corpus.resolve("2024SGHC29")
    assert authority is not None
    assert authority.document_hash
    assert authority.passages[0].text.startswith("must always")
    assert authority.passages[0].assessment_status == "ai_supported"


def test_extractor_accepts_bare_numbered_paragraphs_but_not_citation_years(tmp_path: Path) -> None:
    html = """
    <html><body>
      <h1>Shopee Singapore Pte Ltd v Lim Teck Yong</h1>
      <p>[2024] SGHC 29</p>
      <p>Decision Date : 01 February 2024</p>
      <p>1         The first numbered judgment paragraph.</p>
      <p>A reference to [2007] SGCA 53 does not begin a new paragraph.</p>
      <p>2. The second numbered judgment paragraph.</p>
    </body></html>
    """

    class BareParagraphConnector(FixtureConnector):
        def fetch(self, candidate: SourceCandidate) -> str:
            return html

    class BareParagraphAnnotator:
        def annotate(self, judgment: ExtractedJudgment) -> list[EvidenceAnnotation]:
            return [
                EvidenceAnnotation(
                    paragraph_label="[1]",
                    proposition="legitimate_proprietary_interest",
                    outcome_direction="unknown",
                    confidence=0.6,
                )
            ]

    corpus = ActiveCorpusRepository(tmp_path / "snapshot.json")
    result = CorpusRefreshService(
        corpus,
        Settings(),
        connector=BareParagraphConnector(),
        annotator=BareParagraphAnnotator(),
    ).refresh(new_refresh_run(limit=1))
    assert result.status == "complete"
    authority = corpus.resolve("2024SGHC29")
    assert authority is not None
    assert [item.paragraph_label for item in authority.passages] == ["[1]", "[2]"]
    assert "[2007] SGCA 53" in authority.passages[0].text


def test_deterministic_annotation_fallback_requires_exact_taxonomy_phrase() -> None:
    judgment = JudgmentExtractor().extract(FixtureConnector().candidates[0], HTML)
    annotations = GeminiEvidenceAnnotator(Settings(GEMINI_API_KEY="", OPENROUTER_API_KEY="")).annotate(judgment)
    assert [(item.paragraph_label, item.proposition) for item in annotations] == [
        ("[59]", "legitimate_proprietary_interest")
    ]
    assert annotations[0].annotation_method == "deterministic_taxonomy"


def test_refresh_rejects_an_evidence_free_authority_snapshot(tmp_path: Path) -> None:
    class EmptyAnnotator:
        def annotate(self, judgment: ExtractedJudgment) -> list[EvidenceAnnotation]:
            return []

    corpus = ActiveCorpusRepository(tmp_path / "snapshot.json")
    result = CorpusRefreshService(
        corpus,
        Settings(),
        connector=FixtureConnector(),
        annotator=EmptyAnnotator(),
    ).refresh(new_refresh_run(limit=1))
    assert result.status == "fallback"


def test_official_discovery_parses_html_deduplicates_and_keeps_allowlist() -> None:
    connector = SGCourtsConnector(client=DiscoveryHttpClient(), sleep=lambda _: None)
    profile = TopicProfile(version="test", queries=["employment restraint"])
    candidates = connector.discover(profile, limit=25)
    assert [(candidate.citation_key, candidate.url) for candidate in candidates] == [
        ("2024SGHC29", "https://www.elitigation.sg/gdviewer/s/2024_SGHC_29")
    ]


def test_official_discovery_records_a_missing_robots_policy_without_treating_it_as_disallow() -> None:
    connector = SGCourtsConnector(client=MissingRobotsHttpClient(), sleep=lambda _: None)
    candidates = connector.discover(TopicProfile(version="test", queries=["employment restraint"]), limit=25)
    assert candidates
    assert connector.robots_policy_status == "not_published_404"


def test_invalid_annotation_retains_last_successful_snapshot(tmp_path: Path) -> None:
    corpus = ActiveCorpusRepository(tmp_path / "snapshot.json")
    good = CorpusRefreshService(corpus, Settings(), connector=FixtureConnector(), annotator=FixtureAnnotator()).refresh(new_refresh_run())
    previous_version = good.active_corpus_version
    failed = CorpusRefreshService(corpus, Settings(), connector=FixtureConnector(), annotator=MissingAnchorAnnotator()).refresh(
        new_refresh_run()
    )
    assert failed.status == "fallback"
    assert failed.active_corpus_version == previous_version
    assert corpus.resolve("2024SGHC29") is not None


def test_rejects_heading_mismatch_and_non_allowlisted_urls(tmp_path: Path) -> None:
    corpus = ActiveCorpusRepository(tmp_path / "snapshot.json")
    mismatch = SourceCandidate(
        citation="[2007] SGCA 53",
        citation_key="2007SGCA53",
        url="https://www.elitigation.sg/gd/s/2007_SGCA_53",
        discovery_query="x",
    )
    result = CorpusRefreshService(
        corpus,
        Settings(),
        connector=FixtureConnector([mismatch]),
        annotator=FixtureAnnotator(),
    ).refresh(new_refresh_run())
    assert result.status == "fallback"

    untrusted = SourceCandidate(
        citation="[2024] SGHC 29",
        citation_key="2024SGHC29",
        url="https://example.com/not-a-judgment",
        discovery_query="x",
    )
    result = CorpusRefreshService(
        corpus,
        Settings(),
        connector=FixtureConnector([untrusted]),
        annotator=FixtureAnnotator(),
    ).refresh(new_refresh_run())
    assert result.status == "fallback"


def test_connector_refresh_caps_documents_at_twenty_five(tmp_path: Path) -> None:
    candidates = [
        SourceCandidate(
            citation="[2024] SGHC 29",
            citation_key="2024SGHC29",
            url="https://www.elitigation.sg/gd/s/2024_SGHC_29",
            discovery_query="x",
        )
        for _ in range(30)
    ]
    corpus = ActiveCorpusRepository(tmp_path / "snapshot.json")
    result = CorpusRefreshService(
        corpus,
        Settings(),
        connector=FixtureConnector(candidates),
        annotator=FixtureAnnotator(),
    ).refresh(new_refresh_run(limit=25))
    assert result.accepted_documents <= 25
