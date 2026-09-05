from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Protocol
from urllib import robotparser
from urllib.parse import quote_plus, urljoin, urlparse
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.config import Settings
from app.corpus import TOPIC_PROFILE_VERSION, ActiveCorpusRepository
from app.models import (
    Authority,
    OutcomeDirection,
    Passage,
    RefreshRun,
)
from app.parsers import canonical_citation, normalise_citation
from app.taxonomy import PROPOSITIONS, proposition_for

EXTRACTOR_VERSION = "sgcourts-html-extractor.1"
ANNOTATOR_VERSION = "evidence-annotator.1"
ALLOWED_HOSTS = frozenset({"www.elitigation.sg", "elitigation.sg"})
MAX_DOCUMENTS = 25
REQUEST_INTERVAL_SECONDS = 1.0
CITATION_TEXT = re.compile(r"\[\s*\d{4}\s*\]\s*SG[A-Z()]+\s*\d+", re.IGNORECASE)
CITATION_PATH = re.compile(
    r"(?P<year>\d{4})_(?P<court>SG[A-Z()]+)_(?P<number>\d+)",
    re.IGNORECASE,
)
NUMBERED_PARAGRAPH = re.compile(r"^\s*(?:\[(?P<bracket>\d+)\]|(?P<plain>\d+)\.)\s*(?P<text>.+)$")


class TopicProfile(BaseModel):
    version: str = TOPIC_PROFILE_VERSION
    jurisdiction: str = "Singapore"
    scope: str = "employment restraint of trade"
    queries: list[str]

    @classmethod
    def employment_restraints(cls) -> TopicProfile:
        # The vocabulary is derived from the controlled audit taxonomy. It is
        # intentionally fixed and reviewable rather than a hand-picked case list.
        return cls(
            queries=[
                "Singapore employment restraint of trade restrictive covenant",
                "Singapore employment non-compete legitimate proprietary interest",
                "Singapore employment customer connections trained workforce",
                "Singapore employment restraint geographic duration activity scope",
                "Singapore employment restraint interim injunction",
            ]
        )


@dataclass(frozen=True)
class SourceCandidate:
    citation: str
    citation_key: str
    url: str
    discovery_query: str


@dataclass(frozen=True)
class ExtractedParagraph:
    label: str
    text: str


@dataclass(frozen=True)
class ExtractedJudgment:
    candidate: SourceCandidate
    heading: str
    case_name: str
    court: str
    paragraphs: list[ExtractedParagraph]
    document_hash: str
    retrieved_at: datetime


class SourceConnector(Protocol):
    def discover(self, profile: TopicProfile, limit: int) -> list[SourceCandidate]: ...

    def fetch(self, candidate: SourceCandidate) -> str: ...


class SGCourtsConnector:
    """A bounded connector for official eLitigation judgment pages only."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        base_search_url: str = (
            "https://www.elitigation.sg/gd/Home/Index?CurrentPage=1&Filter=SUPCT&PageSize=0&SearchMode=False&SearchPhrase="
        ),
    ) -> None:
        self.client = client or httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(12.0, connect=6.0),
            headers={"User-Agent": "ProofMark-corpus-refresh/0.2 (hackathon prototype)"},
        )
        self.sleep = sleep
        self.base_search_url = base_search_url
        self._last_request_at: float | None = None
        self._robots_checked = False

    @staticmethod
    def _allowed(url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme == "https" and parsed.hostname in ALLOWED_HOSTS

    def _get(self, url: str) -> httpx.Response:
        if not self._allowed(url):
            raise ValueError("Source URL is not an allowlisted SG Courts host")
        if self._last_request_at is not None:
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < REQUEST_INTERVAL_SECONDS:
                self.sleep(REQUEST_INTERVAL_SECONDS - elapsed)
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self.client.get(url)
                self._last_request_at = time.monotonic()
                response.raise_for_status()
                if "maintenance notice" in response.text.lower():
                    raise RuntimeError("SG Courts search is temporarily unavailable")
                return response
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt < 2:
                    self.sleep(0.5 * (2**attempt))
        raise RuntimeError(f"SG Courts request failed: {type(last_error).__name__}") from last_error

    def discover(self, profile: TopicProfile, limit: int) -> list[SourceCandidate]:
        self._ensure_robots_allow_refresh()
        capped = min(limit, MAX_DOCUMENTS)
        results: list[SourceCandidate] = []
        seen: set[str] = set()
        for query in profile.queries:
            if len(results) >= capped:
                break
            response = self._get(
                f"{self.base_search_url}{quote_plus(query)}"
                "&SearchQueryTime=0&SearchTotalHits=0&SortAscending=False"
                "&SortBy=Score&SpanMultiplePages=False&Verbose=False&YearOfDecision=All"
            )
            soup = BeautifulSoup(response.text, "html.parser")
            for anchor in soup.find_all("a", href=True):
                resolved = urljoin(str(response.url), str(anchor["href"]))
                if not self._allowed(resolved):
                    continue
                path = urlparse(resolved).path.lower()
                if "/gd/s/" not in path and "/gdviewer/s/" not in path:
                    continue
                path_match = CITATION_PATH.search(urlparse(resolved).path)
                citation_text = canonical_citation(anchor.get_text(" ", strip=True))
                if not citation_text and path_match:
                    citation_text = f"[{path_match.group('year')}] {path_match.group('court').upper()} {path_match.group('number')}"
                if not citation_text:
                    continue
                key = normalise_citation(citation_text)
                if key in seen:
                    continue
                seen.add(key)
                results.append(
                    SourceCandidate(
                        citation=citation_text,
                        citation_key=key,
                        url=resolved,
                        discovery_query=query,
                    )
                )
                if len(results) >= capped:
                    break
        return results

    def _ensure_robots_allow_refresh(self) -> None:
        if self._robots_checked:
            return
        robots_url = "https://www.elitigation.sg/robots.txt"
        response = self._get(robots_url)
        parser = robotparser.RobotFileParser()
        parser.parse(response.text.splitlines())
        if not parser.can_fetch("ProofMark-corpus-refresh", self.base_search_url):
            raise RuntimeError("SG Courts robots guidance disallows automated refresh")
        self._robots_checked = True

    def fetch(self, candidate: SourceCandidate) -> str:
        if not self._allowed(candidate.url):
            raise ValueError("Rejected non-allowlisted source candidate")
        return self._get(candidate.url).text


class JudgmentExtractor:
    @staticmethod
    def _visible_lines(html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        for node in soup(["script", "style", "noscript"]):
            node.decompose()
        return [line.strip() for line in soup.get_text("\n").splitlines() if line.strip()]

    def extract(self, candidate: SourceCandidate, html: str) -> ExtractedJudgment:
        if urlparse(candidate.url).hostname not in ALLOWED_HOSTS:
            raise ValueError("Rejected non-allowlisted judgment URL")
        lines = self._visible_lines(html)
        heading_index = next(
            (
                index
                for index, line in enumerate(lines[:120])
                if normalise_citation(line) == candidate.citation_key or candidate.citation_key in normalise_citation(line)
            ),
            None,
        )
        if heading_index is None:
            raise ValueError("Citation does not match a judgment heading")
        heading = lines[heading_index]
        case_name = lines[heading_index - 1] if heading_index > 0 else heading.split(candidate.citation)[0].strip()
        if not case_name or normalise_citation(case_name) == candidate.citation_key:
            case_name = heading.replace(candidate.citation, "").strip(" -–") or candidate.citation

        paragraphs: list[ExtractedParagraph] = []
        current_label: str | None = None
        current_text: list[str] = []
        # A neutral citation also starts with brackets, so never treat the heading
        # itself (or boilerplate before it) as a numbered judgment paragraph.
        for line in lines[heading_index + 1 :]:
            match = NUMBERED_PARAGRAPH.match(line)
            if match:
                if current_label and current_text:
                    paragraphs.append(ExtractedParagraph(current_label, " ".join(current_text)))
                number = match.group("bracket") or match.group("plain")
                current_label = f"[{number}]"
                current_text = [match.group("text")]
            elif current_label:
                current_text.append(line)
        if current_label and current_text:
            paragraphs.append(ExtractedParagraph(current_label, " ".join(current_text)))
        if not paragraphs:
            raise ValueError("No numbered paragraphs were extracted")

        court_code = re.search(r"SG([A-Z()]+)", candidate.citation_key)
        court = f"Singapore {court_code.group(1)}" if court_code else "Singapore Courts"
        return ExtractedJudgment(
            candidate=candidate,
            heading=heading,
            case_name=case_name,
            court=court,
            paragraphs=paragraphs,
            document_hash=hashlib.sha256(html.encode("utf-8")).hexdigest(),
            retrieved_at=datetime.now(UTC),
        )


class EvidenceAnnotation(BaseModel):
    paragraph_label: str
    proposition: str
    limitations: list[str] = Field(default_factory=list, max_length=4)
    outcome_direction: OutcomeDirection
    confidence: float = Field(ge=0, le=1)


class GeminiEvidenceAnnotations(BaseModel):
    annotations: list[EvidenceAnnotation]


class EvidenceAnnotator(Protocol):
    def annotate(self, judgment: ExtractedJudgment) -> list[EvidenceAnnotation]: ...


class GeminiEvidenceAnnotator:
    """Gemini may select labels and taxonomy values, never provide judgment text."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def annotate(self, judgment: ExtractedJudgment) -> list[EvidenceAnnotation]:
        if not self.settings.gemini_api_key:
            raise RuntimeError("Gemini API key is not configured")
        from google import genai
        from google.genai import types

        candidates = []
        for paragraph in judgment.paragraphs:
            proposition, confidence = proposition_for(paragraph.text)
            if proposition != "outside_corpus_scope" or confidence >= 0.55:
                candidates.append(f"{paragraph.label} {paragraph.text}")
        # Bounded source-analysis prompt; normal audit never calls this model.
        excerpts = "\n".join(candidates[:80])[:28_000]
        prompt = (
            "You are annotating extracted paragraphs from one Singapore judgment for a "
            "citation-audit system. Return only paragraph labels present below and only a "
            "controlled proposition. Do not quote, rewrite, invent, assess legal correctness, "
            "or provide a verdict. Select a paragraph only where it materially addresses the "
            f"proposition. Controlled taxonomy: {sorted(PROPOSITIONS)}.\n\n{excerpts}"
        )
        client = genai.Client(
            api_key=self.settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=int(self.settings.gemini_timeout_seconds * 1000)),
        )
        response = client.models.generate_content(
            model=self.settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GeminiEvidenceAnnotations,
                temperature=0,
            ),
        )
        parsed = response.parsed
        if not isinstance(parsed, GeminiEvidenceAnnotations):
            raise ValueError("Gemini returned no schema-valid annotations")
        labels = {item.label for item in judgment.paragraphs}
        cleaned: list[EvidenceAnnotation] = []
        for annotation in parsed.annotations:
            if annotation.paragraph_label not in labels:
                raise ValueError("Gemini selected a paragraph not extracted from this judgment")
            if annotation.proposition not in PROPOSITIONS:
                raise ValueError("Gemini returned a proposition outside the controlled taxonomy")
            cleaned.append(annotation)
        return cleaned


class CorpusRefreshService:
    def __init__(
        self,
        corpus: ActiveCorpusRepository,
        settings: Settings,
        *,
        connector: SourceConnector | None = None,
        extractor: JudgmentExtractor | None = None,
        annotator: EvidenceAnnotator | None = None,
    ) -> None:
        self.corpus = corpus
        self.settings = settings
        self.connector = connector or SGCourtsConnector()
        self.extractor = extractor or JudgmentExtractor()
        self.annotator = annotator or GeminiEvidenceAnnotator(settings)

    def refresh(self, run: RefreshRun) -> RefreshRun:
        started = time.perf_counter()
        run.status = "running"
        run.started_at = datetime.now(UTC)
        profile = TopicProfile.employment_restraints()
        authorities: list[Authority] = []
        try:
            candidates = self.connector.discover(profile, run.requested_limit)
            seen: set[str] = set()
            for candidate in candidates[:MAX_DOCUMENTS]:
                if candidate.citation_key in seen:
                    run.rejected_documents += 1
                    continue
                seen.add(candidate.citation_key)
                try:
                    judgment = self.extractor.extract(candidate, self.connector.fetch(candidate))
                    annotations = self.annotator.annotate(judgment)
                    extracted_labels = {paragraph.label for paragraph in judgment.paragraphs}
                    if any(item.paragraph_label not in extracted_labels for item in annotations):
                        raise ValueError("Annotator selected a paragraph not extracted from this judgment")
                    authorities.append(self._authority_from(judgment, annotations))
                except Exception:
                    # Individual fetch/extract/annotation failure must not contaminate the last snapshot.
                    run.rejected_documents += 1
            if not authorities:
                raise RuntimeError("No source passed provenance and annotation gates")
            metadata = self.corpus.activate(authorities, profile_version=profile.version)
            run.status = "complete"
            run.accepted_documents = len(authorities)
            run.accepted_passages = sum(len(item.passages) for item in authorities)
            run.active_corpus_version = metadata.version
        except Exception as exc:
            previous = self.corpus.get_metadata()
            run.status = "fallback"
            run.fallback_reason = f"Refresh failed ({type(exc).__name__}); retained {previous.version}."
            run.active_corpus_version = previous.version
        run.completed_at = datetime.now(UTC)
        run.duration_ms = round((time.perf_counter() - started) * 1000, 2)
        return run

    def _authority_from(self, judgment: ExtractedJudgment, annotations: list[EvidenceAnnotation]) -> Authority:
        by_label: dict[str, list[EvidenceAnnotation]] = {}
        for annotation in annotations:
            by_label.setdefault(annotation.paragraph_label, []).append(annotation)
        passages: list[Passage] = []
        for paragraph in judgment.paragraphs:
            selected = by_label.get(paragraph.label, [])
            local_proposition, _ = proposition_for(paragraph.text)
            annotations_for_label = [item for item in selected if item.proposition != "outside_corpus_scope"]
            supported = sorted({item.proposition for item in annotations_for_label})
            disagreement = bool(supported and local_proposition != "outside_corpus_scope" and local_proposition not in supported)
            passages.append(
                Passage(
                    id=f"{judgment.candidate.citation_key.lower()}-{paragraph.label.strip('[]')}",
                    paragraph_label=paragraph.label,
                    text=paragraph.text,
                    supported_propositions=supported,
                    limitations=[limit for item in selected for limit in item.limitations],
                    source_provenance="officially_sourced",
                    assessment_status="ai_supported" if supported else "unannotated",
                    annotation_confidence=max((item.confidence for item in selected), default=None),
                    annotation_model=self.settings.gemini_model if selected else None,
                    outcome_direction=selected[0].outcome_direction if selected else "unknown",
                    annotation_disagrees=disagreement,
                )
            )
        return Authority(
            id=judgment.candidate.citation_key.lower(),
            citation=judgment.candidate.citation,
            citation_key=judgment.candidate.citation_key,
            case_name=judgment.case_name,
            court=judgment.court,
            decision_date=datetime.strptime(judgment.candidate.citation[1:5], "%Y").date(),
            official_url=judgment.candidate.url,
            source_status="officially_sourced",
            source_provenance="officially_sourced",
            assessment_status="ai_supported" if annotations else "unannotated",
            source_host=urlparse(judgment.candidate.url).hostname,
            discovery_query=judgment.candidate.discovery_query,
            retrieved_at=judgment.retrieved_at,
            document_hash=judgment.document_hash,
            extractor_version=EXTRACTOR_VERSION,
            passages=passages,
        )


class RefreshManager:
    """Small local background executor. Production moves this work to PGMQ workers."""

    def __init__(
        self,
        service: CorpusRefreshService,
        on_complete: Callable[[RefreshRun], None] | None = None,
    ) -> None:
        self.service = service
        self.on_complete = on_complete
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="proofmark-refresh")
        self._lock = RLock()
        self._latest: RefreshRun | None = None
        self._future: Future[RefreshRun] | None = None

    def start(self, limit: int) -> RefreshRun:
        with self._lock:
            if self._future and not self._future.done():
                return self._latest.model_copy(deep=True)  # type: ignore[union-attr]
            run = RefreshRun(
                public_id=uuid4(),
                status="queued",
                profile_version=TOPIC_PROFILE_VERSION,
                requested_limit=min(limit, MAX_DOCUMENTS),
            )
            self._latest = run
            self._future = self._executor.submit(self._run, run)
            return run.model_copy(deep=True)

    def _run(self, run: RefreshRun) -> RefreshRun:
        result = self.service.refresh(run)
        if self.on_complete:
            self.on_complete(result)
        with self._lock:
            self._latest = result
        return result

    def latest(self) -> RefreshRun | None:
        with self._lock:
            return self._latest.model_copy(deep=True) if self._latest else None


def new_refresh_run(limit: int = MAX_DOCUMENTS) -> RefreshRun:
    return RefreshRun(
        public_id=uuid4(),
        status="queued",
        profile_version=TOPIC_PROFILE_VERSION,
        requested_limit=min(limit, MAX_DOCUMENTS),
    )
