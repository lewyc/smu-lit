from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime
from threading import RLock
from typing import Literal, Protocol
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
from app.structured_model import generate_structured
from app.taxonomy import PHRASE_MAP, PROPOSITIONS, proposition_for

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
NUMBERED_PARAGRAPH = re.compile(
    r"^\s*(?:\[(?P<bracket>\d{1,3})\]|(?P<plain>\d{1,3})(?:\.|\s+))\s*(?P<text>\S.*)$"
)
STANDALONE_PARAGRAPH = re.compile(r"^\s*(?:\[(?P<bracket>\d{1,3})\]|(?P<plain>\d{1,3}))\s*$")
DECISION_DATE = re.compile(r"Decision\s+Date\s*:\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})", re.IGNORECASE)
RESERVED_DATE = re.compile(r"(\d{1,2}\s+[A-Za-z]+\s+\d{4})\s+Judgment\s+reserved", re.IGNORECASE)
CASE_NAME_SIGNAL = re.compile(r"\s(?:v|versus)\s", re.IGNORECASE)


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
    decision_date: date
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
        self.robots_policy_status = "not_checked"

    @staticmethod
    def _allowed(url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme == "https" and parsed.hostname in ALLOWED_HOSTS

    def _get(self, url: str, *, accepted_statuses: frozenset[int] = frozenset()) -> httpx.Response:
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
                if response.status_code not in accepted_statuses:
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
        response = self._get(robots_url, accepted_statuses=frozenset({404}))
        if response.status_code == 404:
            # No robots resource was published. This is not an override of an
            # explicit policy: non-404 failures and explicit disallow rules
            # remain blocking, while the host allowlist and throttle still apply.
            self.robots_policy_status = "not_published_404"
            self._robots_checked = True
            return
        parser = robotparser.RobotFileParser()
        parser.parse(response.text.splitlines())
        if not parser.can_fetch("ProofMark-corpus-refresh", self.base_search_url):
            self.robots_policy_status = "disallowed"
            raise RuntimeError("SG Courts robots guidance disallows automated refresh")
        self.robots_policy_status = "allowed"
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

    @staticmethod
    def _case_name(html: str, lines: list[str], heading_index: int, citation: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        candidates: list[str] = []
        for selector in ("h1", "h2", "h3", "title"):
            candidates.extend(node.get_text(" ", strip=True) for node in soup.select(selector))
        candidates.extend(reversed(lines[max(0, heading_index - 20) : heading_index + 1]))
        vicinity = lines[max(7, heading_index - 10) : heading_index + 26]
        for index, value in enumerate(vicinity):
            if value.casefold() != "v" or index == 0 or index + 1 >= len(vicinity):
                continue
            left = [vicinity[index - 1]]
            if index >= 2 and not vicinity[index - 2].casefold().startswith(
                ("this judgment", "judgments homepage", "close window")
            ) and not CITATION_TEXT.fullmatch(vicinity[index - 2]):
                left.insert(0, vicinity[index - 2])
            candidates.insert(0, f"{'' ''.join(left)} v {vicinity[index + 1]}")
        for value in candidates:
            cleaned = re.sub(re.escape(citation), "", value, flags=re.IGNORECASE).strip(" -–|\t")
            cleaned = re.sub(r"\s+", " ", cleaned)
            cleaned = re.sub(r"(?<=[a-z])Pte\b", " Pte", cleaned)
            if 3 <= len(cleaned) <= 300 and CASE_NAME_SIGNAL.search(cleaned):
                return cleaned
        raise ValueError("Canonical case name was not found near the validated citation heading")

    @staticmethod
    def _decision_date(lines: list[str], citation: str) -> date:
        metadata_text = " ".join(lines[:180])
        match = DECISION_DATE.search(metadata_text) or RESERVED_DATE.search(metadata_text)
        if not match:
            raise ValueError("Decision date was not found in official judgment metadata")
        parsed = datetime.strptime(match.group(1), "%d %B %Y").date()
        if parsed.year != int(citation[1:5]):
            raise ValueError("Decision date year conflicts with the neutral citation")
        return parsed

    def extract(self, candidate: SourceCandidate, html: str) -> ExtractedJudgment:
        if urlparse(candidate.url).hostname not in ALLOWED_HOSTS:
            raise ValueError("Rejected non-allowlisted judgment URL")
        lines = self._visible_lines(html)
        heading_index = next(
            (
                index
                for index, line in enumerate(lines[:120])
                if index > 0
                and (
                    normalise_citation(line) == candidate.citation_key
                    or candidate.citation_key in normalise_citation(line)
                )
            ),
            None,
        )
        if heading_index is None:
            raise ValueError("Citation does not match a judgment heading")
        heading = lines[heading_index]
        case_name = self._case_name(html, lines, heading_index, candidate.citation)
        decision_date = self._decision_date(lines, candidate.citation)

        paragraphs: list[ExtractedParagraph] = []
        current_label: str | None = None
        current_text: list[str] = []
        # A neutral citation also starts with brackets, so never treat the heading
        # itself (or boilerplate before it) as a numbered judgment paragraph.
        body_lines = lines[heading_index + 1 :]
        parsed_lines = [
            (line, NUMBERED_PARAGRAPH.match(line), STANDALONE_PARAGRAPH.match(line)) for line in body_lines
        ]
        first_paragraph = next(
            (
                index
                for index, (_, match, standalone) in enumerate(parsed_lines)
                if (
                    match
                    and int(match.group("bracket") or match.group("plain")) == 1
                    or standalone
                    and int(standalone.group("bracket") or standalone.group("plain")) == 1
                    and index + 1 < len(parsed_lines)
                    and not parsed_lines[index + 1][0].casefold().startswith("foot note")
                )
            ),
            None,
        )
        if first_paragraph is not None:
            parsed_lines = parsed_lines[first_paragraph:]
        current_number: int | None = None
        for index, (line, match, standalone) in enumerate(parsed_lines):
            if match:
                number = int(match.group("bracket") or match.group("plain"))
                if current_number is not None and number != current_number + 1:
                    current_text.append(line)
                    continue
                if current_label and current_text:
                    paragraphs.append(ExtractedParagraph(current_label, " ".join(current_text)))
                current_label = f"[{number}]"
                current_number = number
                current_text = [match.group("text")]
            elif standalone:
                number = int(standalone.group("bracket") or standalone.group("plain"))
                next_is_footnote = index + 1 < len(parsed_lines) and parsed_lines[index + 1][0].casefold().startswith(
                    "foot note"
                )
                if current_number is None or number != current_number + 1 or next_is_footnote:
                    if current_label:
                        current_text.append(line)
                    continue
                if current_label and current_text:
                    paragraphs.append(ExtractedParagraph(current_label, " ".join(current_text)))
                current_label = f"[{number}]"
                current_number = number
                current_text = []
            elif current_label:
                current_text.append(line)
        if current_label and current_text:
            paragraphs.append(ExtractedParagraph(current_label, " ".join(current_text)))
        if not paragraphs:
            raise ValueError("No numbered paragraphs were extracted")

        court_code = re.search(r"SG([A-Z()]+)", candidate.citation_key)
        code = court_code.group(1) if court_code else ""
        court = {"CA": "Court of Appeal", "HC": "High Court", "HC(A)": "Appellate Division of the High Court"}.get(
            code,
            f"Singapore {code}" if code else "Singapore Courts",
        )
        return ExtractedJudgment(
            candidate=candidate,
            heading=heading,
            case_name=case_name,
            court=court,
            decision_date=decision_date,
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
    annotation_method: Literal["structured_model", "deterministic_taxonomy"] = "structured_model"


class GeminiEvidenceAnnotations(BaseModel):
    annotations: list[EvidenceAnnotation]


class EvidenceAnnotator(Protocol):
    def annotate(self, judgment: ExtractedJudgment) -> list[EvidenceAnnotation]: ...


class GeminiEvidenceAnnotator:
    """A model proposes labels; exact taxonomy phrases provide a conservative fallback."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def annotate(self, judgment: ExtractedJudgment) -> list[EvidenceAnnotation]:
        if self.settings.has_structured_model_key:
            try:
                annotations = self._from_structured_model(judgment)
                if annotations:
                    return annotations
            except Exception:
                # A model outage or an empty schema-valid result must not activate
                # an evidence-free snapshot. The bounded deterministic pass below
                # still requires exact taxonomy phrases in official text.
                pass
        return self._from_deterministic_taxonomy(judgment)

    def _from_structured_model(self, judgment: ExtractedJudgment) -> list[EvidenceAnnotation]:
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
        parsed = generate_structured(
            self.settings,
            model=self.settings.annotation_model,
            prompt=prompt,
            response_schema=GeminiEvidenceAnnotations,
        )
        if not isinstance(parsed, GeminiEvidenceAnnotations):
            raise ValueError("Structured model returned no schema-valid annotations")
        labels = {item.label for item in judgment.paragraphs}
        cleaned: list[EvidenceAnnotation] = []
        for annotation in parsed.annotations:
            if annotation.paragraph_label not in labels:
                raise ValueError("Gemini selected a paragraph not extracted from this judgment")
            if annotation.proposition not in PROPOSITIONS:
                raise ValueError("Gemini returned a proposition outside the controlled taxonomy")
            cleaned.append(annotation.model_copy(update={"annotation_method": "structured_model"}))
        return cleaned

    @staticmethod
    def _from_deterministic_taxonomy(judgment: ExtractedJudgment) -> list[EvidenceAnnotation]:
        """Create bounded, review-only labels from exact controlled-taxonomy phrases."""
        annotations: list[EvidenceAnnotation] = []
        for paragraph in judgment.paragraphs:
            lowered = paragraph.text.casefold()
            propositions = {
                proposition
                for phrases, proposition in PHRASE_MAP
                if proposition != "outside_corpus_scope" and any(phrase in lowered for phrase in phrases)
            }
            for proposition in sorted(propositions):
                annotations.append(
                    EvidenceAnnotation(
                        paragraph_label=paragraph.label,
                        proposition=proposition,
                        limitations=["Deterministic taxonomy phrase match; lawyer review required."],
                        outcome_direction="unknown",
                        confidence=0.55,
                        annotation_method="deterministic_taxonomy",
                    )
                )
                if len(annotations) >= 40:
                    return annotations
        return annotations


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
                    if not annotations:
                        raise ValueError("No proposition-linked evidence annotations were retained for this judgment")
                    extracted_labels = {paragraph.label for paragraph in judgment.paragraphs}
                    if any(item.paragraph_label not in extracted_labels for item in annotations):
                        raise ValueError("Annotator selected a paragraph not extracted from this judgment")
                    authorities.append(self._authority_from(judgment, annotations))
                except Exception:
                    # Individual fetch/extract/annotation failure must not contaminate the last snapshot.
                    run.rejected_documents += 1
            if not authorities or not any(
                passage.supported_propositions for authority in authorities for passage in authority.passages
            ):
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
        run.robots_policy_status = self._robots_policy_status()
        run.completed_at = datetime.now(UTC)
        run.duration_ms = round((time.perf_counter() - started) * 1000, 2)
        return run

    def _robots_policy_status(self) -> str:
        connector = self.connector
        status = getattr(connector, "robots_policy_status", None)
        if status is None:
            status = getattr(getattr(connector, "delegate", None), "robots_policy_status", None)
        return status if status in {"not_checked", "allowed", "not_published_404", "disallowed"} else "not_checked"

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
            methods = {item.annotation_method for item in annotations_for_label}
            assessment_status = (
                "ai_supported"
                if "structured_model" in methods
                else "deterministically_supported"
                if supported
                else "unannotated"
            )
            disagreement = bool(supported and local_proposition != "outside_corpus_scope" and local_proposition not in supported)
            passages.append(
                Passage(
                    id=f"{judgment.candidate.citation_key.lower()}-{paragraph.label.strip('[]')}",
                    paragraph_label=paragraph.label,
                    text=paragraph.text,
                    supported_propositions=supported,
                    limitations=[limit for item in selected for limit in item.limitations],
                    source_provenance="officially_sourced",
                    assessment_status=assessment_status,
                    annotation_confidence=max((item.confidence for item in selected), default=None),
                    annotation_model=(
                        self.settings.annotation_model
                        if "structured_model" in methods
                        else "deterministic-taxonomy-2.0"
                        if supported
                        else None
                    ),
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
            decision_date=judgment.decision_date,
            official_url=judgment.candidate.url,
            source_status="officially_sourced",
            source_provenance="officially_sourced",
            assessment_status=(
                "ai_supported"
                if any(item.annotation_method == "structured_model" for item in annotations)
                else "deterministically_supported"
            ),
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
