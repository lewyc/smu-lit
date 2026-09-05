from pathlib import Path

import httpx

from app.config import Settings
from app.corpus import ActiveCorpusRepository
from app.refresh import (
    CorpusRefreshService,
    EvidenceAnnotation,
    ExtractedJudgment,
    SGCourtsConnector,
    SourceCandidate,
    TopicProfile,
    new_refresh_run,
)

HTML = """
<html><body>
  <h1>Example Employer Pte Ltd v Example Employee</h1>
  <p>[2025] SGHC 101</p>
  <p>[1] A restraint must protect a legitimate proprietary interest.</p>
  <p>[2] The inquiry remains fact-sensitive.</p>
</body></html>
"""


class FixtureConnector:
    def __init__(self, candidates: list[SourceCandidate] | None = None) -> None:
        self.candidates = candidates or [
            SourceCandidate(
                citation="[2025] SGHC 101",
                citation_key="2025SGHC101",
                url="https://www.elitigation.sg/gd/s/2025_SGHC_101",
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
                paragraph_label="[1]",
                proposition="legitimate_proprietary_interest",
                limitations=["Fact-sensitive."],
                outcome_direction="mixed",
                confidence=0.91,
            )
        ]


class InventedLabelAnnotator:
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
                '<a href="/gdviewer/s/2025_SGHC_101">Example [2025] SGHC 101</a>'
                '<a href="/gdviewer/s/2025_SGHC_101">Duplicate [2025] SGHC 101</a>'
                '<a href="https://example.com/gdviewer/s/2025_SGHC_999">Reject</a>'
            ),
            request=httpx.Request("GET", url),
        )


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
    authority = corpus.resolve("2025SGHC101")
    assert authority is not None
    assert authority.document_hash
    assert authority.passages[0].text.startswith("A restraint")
    assert authority.passages[0].assessment_status == "ai_supported"


def test_official_discovery_parses_html_deduplicates_and_keeps_allowlist() -> None:
    connector = SGCourtsConnector(client=DiscoveryHttpClient(), sleep=lambda _: None)
    profile = TopicProfile(version="test", queries=["employment restraint"])
    candidates = connector.discover(profile, limit=25)
    assert [(candidate.citation_key, candidate.url) for candidate in candidates] == [
        ("2025SGHC101", "https://www.elitigation.sg/gdviewer/s/2025_SGHC_101")
    ]


def test_invalid_annotation_retains_last_successful_snapshot(tmp_path: Path) -> None:
    corpus = ActiveCorpusRepository(tmp_path / "snapshot.json")
    good = CorpusRefreshService(corpus, Settings(), connector=FixtureConnector(), annotator=FixtureAnnotator()).refresh(new_refresh_run())
    previous_version = good.active_corpus_version
    failed = CorpusRefreshService(corpus, Settings(), connector=FixtureConnector(), annotator=InventedLabelAnnotator()).refresh(
        new_refresh_run()
    )
    assert failed.status == "fallback"
    assert failed.active_corpus_version == previous_version
    assert corpus.resolve("2025SGHC101") is not None


def test_rejects_heading_mismatch_and_non_allowlisted_urls(tmp_path: Path) -> None:
    corpus = ActiveCorpusRepository(tmp_path / "snapshot.json")
    mismatch = SourceCandidate(
        citation="[2025] SGHC 999",
        citation_key="2025SGHC999",
        url="https://www.elitigation.sg/gd/s/2025_SGHC_999",
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
        citation="[2025] SGHC 101",
        citation_key="2025SGHC101",
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
            citation=f"[2025] SGHC {number}",
            citation_key=f"2025SGHC{number}",
            url=f"https://www.elitigation.sg/gd/s/2025_SGHC_{number}",
            discovery_query="x",
        )
        for number in range(1, 31)
    ]
    corpus = ActiveCorpusRepository(tmp_path / "snapshot.json")
    result = CorpusRefreshService(
        corpus,
        Settings(),
        connector=FixtureConnector(candidates),
        annotator=FixtureAnnotator(),
    ).refresh(new_refresh_run(limit=25))
    assert result.accepted_documents <= 25
