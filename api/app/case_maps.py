from __future__ import annotations

import hashlib
import io
import re
from datetime import UTC, date, datetime
from threading import RLock
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel

from app.config import Settings
from app.models import (
    AnnotationRevision,
    Authority,
    CaseMapAnnotation,
    CaseMapDetail,
    CaseMapFieldProvenance,
    FeedbackResolution,
    FeedbackSubmission,
    Passage,
    PractitionerFeedback,
)
from app.parsers import canonical_citation, normalise_citation
from app.taxonomy import PROPOSITIONS

CASE_MAP_SCHEMA_VERSION = "proofmark-case-map-1.0"
CASE_MAP_PROMPT_VERSION = "sg-rot-casemap-prompt-1.0"
CASE_MAP_ANNOTATOR_VERSION = "proofmark-casemap-annotator-1.0"
PDF_MAX_BYTES = 15 * 1024 * 1024
ROLE_TIERS = {
    "party_submission": "B",
    "procedural_history": "B",
    "disposition": "B",
    "ratio_candidate": "C",
    "holding": "C",
    "obiter_candidate": "C",
    "factual_finding": "C",
}


class CaseMapAnnotations(BaseModel):
    annotations: list[CaseMapAnnotation]


class CaseMapRepository(Protocol):
    def create(self, case_map: CaseMapDetail) -> CaseMapDetail: ...
    def get(self, public_id: UUID) -> CaseMapDetail | None: ...
    def list(self) -> list[CaseMapDetail]: ...
    def replace(self, case_map: CaseMapDetail) -> CaseMapDetail: ...


class LocalCaseMapRepository:
    def __init__(self) -> None:
        self._maps: dict[UUID, CaseMapDetail] = {}
        self._lock = RLock()

    def create(self, case_map: CaseMapDetail) -> CaseMapDetail:
        with self._lock:
            self._maps[case_map.public_id] = case_map.model_copy(deep=True)
        return case_map

    def get(self, public_id: UUID) -> CaseMapDetail | None:
        with self._lock:
            value = self._maps.get(public_id)
            return value.model_copy(deep=True) if value else None

    def list(self) -> list[CaseMapDetail]:
        with self._lock:
            return sorted(
                (item.model_copy(deep=True) for item in self._maps.values()),
                key=lambda item: item.updated_at,
                reverse=True,
            )

    def replace(self, case_map: CaseMapDetail) -> CaseMapDetail:
        return self.create(case_map)


class CaseMapValidator:
    @staticmethod
    def _normalise_text(value: str) -> str:
        return " ".join(value.split()).casefold()

    def validate(self, authority: Authority, annotations: list[CaseMapAnnotation]) -> tuple[list[CaseMapAnnotation], list[str]]:
        paragraph_by_label = {item.paragraph_label: item for item in authority.passages}
        validated: list[CaseMapAnnotation] = []
        errors: list[str] = []
        for annotation in annotations:
            messages: list[str] = []
            expected_tier = ROLE_TIERS[annotation.annotation_type]
            if annotation.provenance and annotation.provenance.tier != expected_tier:
                messages.append(
                    f"Provenance tier {annotation.provenance.tier} is inconsistent with the {annotation.annotation_type} role."
                )
            if annotation.proposition_code and annotation.proposition_code not in PROPOSITIONS:
                messages.append("Proposition is outside the controlled taxonomy.")
            selected = [paragraph_by_label.get(label) for label in annotation.paragraph_labels]
            if any(item is None for item in selected):
                messages.append("One or more paragraph labels do not belong to this judgment snapshot.")
            selected_text = " ".join(item.text for item in selected if item)
            if self._normalise_text(annotation.supporting_quote) not in self._normalise_text(selected_text):
                messages.append("Supporting quotation is not present in the selected stored paragraphs.")
            if annotation.annotation_type in {"ratio_candidate", "obiter_candidate"} and not annotation.paragraph_labels:
                messages.append("Ratio and obiter candidates require paragraph evidence.")
            if annotation.annotation_type == "party_submission" and annotation.statement.lower().startswith("the court held"):
                messages.append("A party submission cannot be represented as a court holding.")
            status = "invalid" if messages else "valid"
            validated_item = annotation.model_copy(update={"validation_status": status, "validation_messages": messages})
            validated.append(validated_item)
            errors.extend(f"{annotation.id}: {message}" for message in messages)
        return validated, errors


class CaseMapAnnotator:
    """Gemini proposes anchored labels; a deterministic fallback keeps the demo available."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def annotate(self, authority: Authority, selected_passages: list[Passage]) -> tuple[list[CaseMapAnnotation], str]:
        if self.settings.gemini_api_key:
            try:
                return self._gemini(authority, selected_passages), self.settings.gemini_casemap_model
            except Exception:
                pass
        annotations = []
        for passage in selected_passages:
            proposition = passage.supported_propositions[0] if passage.supported_propositions else None
            annotations.append(
                CaseMapAnnotation(
                    id=f"local-{passage.id}",
                    annotation_type="holding",
                    proposition_code=proposition,
                    statement=passage.text,
                    paragraph_labels=[passage.paragraph_label],
                    supporting_quote=passage.text[:800],
                    modality="qualified" if passage.limitations else "descriptive",
                    limitations=passage.limitations,
                    applicability_factors=[],
                    model_confidence=0.55,
                )
            )
        return annotations, "local-deterministic-fallback"

    def _gemini(self, authority: Authority, passages: list[Passage]) -> list[CaseMapAnnotation]:
        from google import genai
        from google.genai import types

        source = "\n".join(f"{item.paragraph_label} {item.text}" for item in passages)
        prompt = (
            "Create a draft Case Map using only the supplied paragraphs. Every supporting_quote must be an exact short "
            "substring and every paragraph label must be copied exactly. Do not decide verdicts, currency, or binding status. "
            "Cover issues, material facts, procedural stage, party submissions, court findings, disposition, candidate ratio "
            "and obiter, qualifications, policy considerations, factual distinctions, and cited authorities where the supplied "
            "paragraphs contain them. Do not invent a category that is absent. "
            f"Controlled propositions: {sorted(PROPOSITIONS)}. Case: {authority.case_name} {authority.citation}.\n\n{source}"
        )
        client = genai.Client(
            api_key=self.settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=int(self.settings.gemini_timeout_seconds * 1000)),
        )
        response = client.models.generate_content(
            model=self.settings.gemini_casemap_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CaseMapAnnotations,
                temperature=0,
            ),
        )
        if not isinstance(response.parsed, CaseMapAnnotations):
            raise ValueError("Gemini returned no schema-valid Case Map")
        return response.parsed.annotations


class CaseMapService:
    def __init__(self, settings: Settings, corpus, repository: CaseMapRepository | None = None) -> None:
        self.settings = settings
        self.corpus = corpus
        self.repository = repository or LocalCaseMapRepository()
        self.annotator = CaseMapAnnotator(settings)
        self.validator = CaseMapValidator()
        self._imports: dict[tuple[str, str], Authority] = {}

    @staticmethod
    def _hash(authority: Authority) -> str:
        if authority.document_hash:
            return authority.document_hash
        payload = "\n".join(f"{p.paragraph_label}:{p.text}" for p in authority.passages)
        return hashlib.sha256(payload.encode()).hexdigest()

    def generate(self, citation: str, authority_override: Authority | None = None) -> CaseMapDetail:
        authority = authority_override or self.corpus.resolve(normalise_citation(citation))
        if authority is None:
            raise LookupError("Authority is not present in the active immutable snapshot")
        annotations, model = self.annotator.annotate(authority, authority.passages)
        annotations = [
            annotation.model_copy(
                update={
                    "paragraph_labels": [self._canonical_label(label) for label in annotation.paragraph_labels],
                    "provenance": self._provenance(annotation, model),
                }
            )
            for annotation in annotations
        ]
        annotations = self._deduplicate(annotations)
        validated, errors = self.validator.validate(authority, annotations)
        now = datetime.now(UTC)
        case_map = CaseMapDetail(
            public_id=uuid4(),
            citation=authority.citation,
            citation_key=authority.citation_key,
            case_name=authority.case_name,
            document_hash=self._hash(authority),
            schema_version=CASE_MAP_SCHEMA_VERSION,
            source_provenance=authority.source_provenance,
            source_url=authority.official_url,
            model=model,
            prompt_version=CASE_MAP_PROMPT_VERSION,
            annotator_version=CASE_MAP_ANNOTATOR_VERSION,
            extractor_version=authority.extractor_version,
            annotations=validated,
            validation_errors=errors,
            source_paragraphs=authority.passages,
            created_at=now,
            updated_at=now,
        )
        return self.repository.create(case_map)

    @staticmethod
    def _deduplicate(annotations: list[CaseMapAnnotation]) -> list[CaseMapAnnotation]:
        merged: dict[tuple[str, str | None, tuple[str, ...]], CaseMapAnnotation] = {}
        for item in annotations:
            key = (item.annotation_type, item.proposition_code, tuple(sorted(item.paragraph_labels)))
            if key not in merged:
                merged[key] = item
                continue
            current = merged[key]
            merged[key] = current.model_copy(
                update={
                    "limitations": sorted(set(current.limitations + item.limitations)),
                    "applicability_factors": sorted(set(current.applicability_factors + item.applicability_factors)),
                    "model_confidence": max(current.model_confidence, item.model_confidence),
                }
            )
        return list(merged.values())

    @staticmethod
    def _canonical_label(label: str) -> str:
        numbers = [int(value) for value in re.findall(r"\d+", label)]
        if len(numbers) >= 2:
            return f"[{numbers[0]}]-[{numbers[1]}]"
        return f"[{numbers[0]}]" if numbers else label

    @staticmethod
    def _provenance(
        annotation: CaseMapAnnotation,
        model: str,
        *,
        previous: CaseMapFieldProvenance | None = None,
    ) -> CaseMapFieldProvenance:
        method = "rule_based" if model == "local-deterministic-fallback" else "model"
        if previous:
            method = "hybrid"
        return CaseMapFieldProvenance(
            field=annotation.annotation_type,
            tier=ROLE_TIERS[annotation.annotation_type],
            extraction_method=method,
            confidence=annotation.model_confidence,
            human_verified=False,
            supporting_evidence=annotation.paragraph_labels,
            version=(previous.version + 1) if previous else 1,
        )

    def list(self) -> list[CaseMapDetail]:
        maps = self.repository.list()
        current_hashes = {item.citation_key: self._hash(item) for item in self.corpus.list_authorities()}
        for item in maps:
            if item.source_provenance != "user_supplied" and current_hashes.get(item.citation_key) != item.document_hash:
                item.status = "stale"
        return maps

    def get(self, public_id: UUID) -> CaseMapDetail | None:
        item = self.repository.get(public_id)
        if not item:
            return None
        if item.source_provenance != "user_supplied":
            authority = self.corpus.resolve(item.citation_key)
            if not authority or self._hash(authority) != item.document_hash:
                item.status = "stale"
        return item

    def revise(self, public_id: UUID, annotation_id: str, revision: AnnotationRevision) -> CaseMapDetail:
        item = self.get(public_id)
        if not item:
            raise LookupError("Case Map not found")
        if item.status == "stale":
            raise ValueError("A stale Case Map cannot be revised")
        authority = self._authority_for(item)
        annotations = []
        found = False
        for annotation in item.annotations:
            if annotation.id == annotation_id:
                found = True
                previous_provenance = annotation.provenance
                annotation = annotation.model_copy(update=revision.model_dump(exclude_none=True))
                annotation.provenance = self._provenance(
                    annotation,
                    item.model,
                    previous=previous_provenance,
                )
            annotations.append(annotation)
        if not found:
            raise LookupError("Annotation not found")
        validated, errors = self.validator.validate(authority, annotations)
        now = datetime.now(UTC)
        item.status = "superseded"
        item.updated_at = now
        self.repository.replace(item)
        history = item.revision_history + [
            {
                "event": "annotation_revised",
                "annotation_id": annotation_id,
                "supersedes": str(item.public_id),
                "at": now.isoformat(),
            }
        ]
        revised = item.model_copy(
            deep=True,
            update={
                "public_id": uuid4(),
                "annotations": [annotation.model_copy(update={"review_status": "draft"}) for annotation in validated],
                "validation_errors": errors,
                "version": item.version + 1,
                "status": "draft",
                "created_at": now,
                "updated_at": now,
                "reviewer_id": None,
                "reviewed_at": None,
                "revision_history": history,
            },
        )
        return self.repository.create(revised)

    def approve(self, public_id: UUID, reviewer_id: UUID | None = None) -> CaseMapDetail:
        item = self.get(public_id)
        if not item:
            raise LookupError("Case Map not found")
        if item.status == "stale":
            raise ValueError("A stale Case Map cannot be approved")
        if item.validation_errors or any(a.validation_status == "invalid" for a in item.annotations):
            raise ValueError("Invalid annotations cannot be approved")
        now = datetime.now(UTC)
        item.status = "approved"
        item.reviewer_id = reviewer_id
        item.reviewed_at = now
        item.updated_at = now
        item.annotations = [
            a.model_copy(
                update={
                    "review_status": "approved",
                    "provenance": (
                        a.provenance.model_copy(
                            update={
                                "human_verified": True,
                                "verified_by": reviewer_id,
                                "extraction_method": "hybrid"
                                if a.provenance.extraction_method in {"model", "rule_based"}
                                else a.provenance.extraction_method,
                            }
                        )
                        if a.provenance
                        else None
                    ),
                }
            )
            for a in item.annotations
        ]
        item.revision_history.append({"event": "approved", "reviewer_id": str(reviewer_id) if reviewer_id else None, "at": now.isoformat()})
        return self.repository.replace(item)

    def _authority_for(self, item: CaseMapDetail) -> Authority:
        authority = (
            self._imports.get((item.citation_key, item.document_hash))
            if item.source_provenance == "user_supplied"
            else self.corpus.resolve(item.citation_key)
        )
        if not authority:
            raise LookupError("Source judgment snapshot is unavailable")
        return authority

    def import_pdf(self, content: bytes, filename: str, expected_citation: str, official_url: str | None = None) -> CaseMapDetail:
        if len(content) > PDF_MAX_BYTES:
            raise ValueError("PDF exceeds the 15 MB limit")
        if not content.startswith(b"%PDF"):
            raise ValueError("The upload is not a valid PDF")
        from pypdf import PdfReader

        try:
            reader = PdfReader(io.BytesIO(content))
        except Exception as exc:
            raise ValueError("Malformed PDF") from exc
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if len(text.strip()) < 80:
            raise ValueError("No usable text was found; scanned PDFs require OCR and are not supported")
        canonical = canonical_citation(expected_citation)
        if not canonical:
            raise ValueError("A valid expected Singapore neutral citation is required")
        paragraphs = self._numbered_paragraphs(text)
        if not paragraphs:
            raise ValueError("The PDF does not contain recognisable numbered paragraphs")
        citation_key = normalise_citation(canonical)
        year = int(canonical[1:5])
        court_code = canonical.split()[1]
        digest = hashlib.sha256(content).hexdigest()
        authority = Authority(
            id=f"pdf-{digest[:12]}",
            citation=canonical,
            citation_key=citation_key,
            case_name=filename.rsplit(".", 1)[0],
            court=court_code,
            decision_date=date(year, 1, 1),
            official_url=official_url or "https://www.elitigation.sg/gd/",
            source_status="user_supplied",
            source_provenance="user_supplied",
            assessment_status="unannotated",
            document_hash=digest,
            extractor_version="pypdf-numbered-paragraphs-1.0",
            passages=paragraphs,
        )
        self._imports[(citation_key, digest)] = authority
        return self.generate(canonical, authority)

    @staticmethod
    def _numbered_paragraphs(text: str) -> list[Passage]:
        matches = list(re.finditer(r"(?m)^\s*(?:\[(\d+)\]|(\d+)\.)\s+", text))
        passages: list[Passage] = []
        for index, match in enumerate(matches):
            number = match.group(1) or match.group(2)
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            body = " ".join(text[match.end() : end].split())
            if body:
                passages.append(
                    Passage(
                        id=f"pdf-{number}",
                        paragraph_label=f"[{number}]",
                        text=body,
                        supported_propositions=[],
                        source_provenance="user_supplied",
                        assessment_status="unannotated",
                    )
                )
        return passages


class LocalFeedbackRepository:
    def __init__(self) -> None:
        self._items: dict[UUID, PractitionerFeedback] = {}
        self._lock = RLock()

    def submit(self, submission: FeedbackSubmission) -> PractitionerFeedback:
        item = PractitionerFeedback(public_id=uuid4(), created_at=datetime.now(UTC), **submission.model_dump())
        with self._lock:
            self._items[item.public_id] = item
        return item

    def list(self) -> list[PractitionerFeedback]:
        with self._lock:
            return sorted(self._items.values(), key=lambda item: item.created_at, reverse=True)

    def resolve(self, public_id: UUID, resolution: FeedbackResolution, reviewer_id: UUID | None = None) -> PractitionerFeedback:
        with self._lock:
            item = self._items.get(public_id)
            if not item:
                raise LookupError("Feedback not found")
            item.status = resolution.decision
            item.resolution_note = resolution.resolution_note
            item.resolved_by = reviewer_id
            item.resolved_at = datetime.now(UTC)
            return item
