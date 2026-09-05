from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from app.config import Settings
from app.corpus import ActiveCorpusRepository
from app.models import (
    AuditDetail,
    AuditSummary,
    CaseMapDetail,
    LegalCurrencyRecord,
    LegalCurrencyRecordSubmission,
    PractitionerFeedback,
    RefreshRun,
)
from app.parsers import normalise_citation


class AuditRepository(Protocol):
    def save(self, audit: AuditDetail) -> AuditDetail: ...

    def get(self, public_id: UUID) -> AuditDetail | None: ...

    def list(self) -> list[AuditSummary]: ...

    def find_cached(self, cache_key: str) -> AuditDetail | None: ...

    def delete(self, public_id: UUID) -> bool: ...


class LocalAuditRepository:
    def __init__(self) -> None:
        self._audits: dict[UUID, AuditDetail] = {}

    def save(self, audit: AuditDetail) -> AuditDetail:
        self._audits[audit.public_id] = audit
        return audit

    def get(self, public_id: UUID) -> AuditDetail | None:
        return self._audits.get(public_id)

    def list(self) -> list[AuditSummary]:
        audits = sorted(self._audits.values(), key=lambda item: item.created_at, reverse=True)
        return [AuditSummary(**item.model_dump()) for item in audits]

    def find_cached(self, cache_key: str) -> AuditDetail | None:
        matches = [audit for audit in self._audits.values() if audit.audit_cache_key == cache_key]
        return max(matches, key=lambda item: item.created_at).model_copy(deep=True) if matches else None

    def delete(self, public_id: UUID) -> bool:
        return self._audits.pop(public_id, None) is not None


class SupabaseAuditRepository:
    """Server-side repository. The secret key must never be used by the dashboard."""

    def __init__(self, settings: Settings, bearer_token: str) -> None:
        from supabase import create_client

        self.settings = settings
        if not settings.supabase_secret_key:
            raise RuntimeError("Supabase server-side secret is not configured")
        self.client = create_client(settings.supabase_url, settings.supabase_secret_key)
        auth_response = self.client.auth.get_user(bearer_token)
        if not auth_response.user:
            raise PermissionError("Invalid Supabase bearer token")
        self.user_id = str(auth_response.user.id)
        membership = self.client.table("organisation_members").select("organisation_id,role").eq("user_id", self.user_id).limit(1).execute()
        if not membership.data:
            raise PermissionError("The signed-in user has no ProofMark organisation")
        self.organisation_id = membership.data[0]["organisation_id"]
        self.role = membership.data[0]["role"]

    def save(self, audit: AuditDetail) -> AuditDetail:
        retention_expires_at = datetime.now(UTC) + timedelta(days=self.settings.audit_retention_days)
        re_audited_from_id = None
        if audit.re_audited_from_public_id:
            previous = (
                self.client.table("audit_runs")
                .select("id")
                .eq("organisation_id", self.organisation_id)
                .eq("public_id", str(audit.re_audited_from_public_id))
                .maybe_single()
                .execute()
            )
            if not previous.data:
                raise PermissionError("The source audit is not in the signed-in organisation")
            re_audited_from_id = previous.data["id"]
        run_payload = {
            "organisation_id": self.organisation_id,
            "created_by": self.user_id,
            "public_id": str(audit.public_id),
            "input_text": audit.input_text,
            "status": "complete",
            "corpus_version": audit.corpus_version,
            "engine_version": audit.engine_version,
            "parser_mode": audit.parser_used,
            "parser_version": audit.parser_version,
            "audit_cache_key": audit.audit_cache_key,
            "cache_status": audit.cache_status,
            "source_checked_at": audit.source_checked_at.isoformat() if audit.source_checked_at else None,
            "currency_registry_version": audit.currency_registry_version,
            "retention_expires_at": retention_expires_at.isoformat(),
            "re_audited_from_id": re_audited_from_id,
            "processing_duration_ms": audit.processing_duration_ms,
            "summary_metrics": audit.metrics.model_dump(),
            "summary_counts": audit.summary_counts,
            "audit_mode": audit.audit_mode,
            "original_question": audit.original_question,
            "facts": audit.facts,
            "module_scores": {
                "citation": audit.metrics.citation_integrity_module.model_dump() if audit.metrics.citation_integrity_module else None,
                "proposition": (
                    audit.metrics.propositional_accuracy_module.model_dump() if audit.metrics.propositional_accuracy_module else None
                ),
                "currency": audit.metrics.relevance_currency_module.model_dump() if audit.metrics.relevance_currency_module else None,
                "balance": audit.metrics.balance_completeness_module.model_dump() if audit.metrics.balance_completeness_module else None,
                "overall": audit.metrics.overall_score,
            },
            "evaluation_provenance": audit.evaluation_provenance,
            "result_payload": audit.model_dump(mode="json"),
            "completed_at": audit.created_at.isoformat(),
        }
        run_response = self.client.table("audit_runs").insert(run_payload).execute()
        run_id = run_response.data[0]["id"]
        claim_rows = []
        for claim in audit.claims:
            claim_rows.append(
                {
                    "audit_run_id": run_id,
                    "claim_order": claim.order,
                    "claim_text": claim.text,
                    "citation": claim.citation,
                    "pinpoint": claim.pinpoint,
                    "proposition_code": claim.proposition,
                    "parser_confidence": claim.parser_confidence,
                    "parser_used": claim.parser_used,
                    "verdict": claim.verdict,
                    "rationale": claim.rationale,
                    "missing_evidence": claim.missing_evidence,
                    "escalation_required": claim.lawyer_review_required,
                    "pinpoint_status": claim.pinpoint_status,
                    "quote_status": claim.quote_status,
                    "citation_identity_status": claim.citation_identity_status,
                    "source_role_status": claim.source_role_status,
                    "currency_status": claim.currency_status,
                }
            )
        claim_response = self.client.table("audit_claims").insert(claim_rows).execute()
        claim_ids = {row["claim_order"]: row["id"] for row in claim_response.data}
        evidence_rows = []
        for claim in audit.claims:
            for evidence in claim.evidence:
                evidence_rows.append(
                    {
                        "audit_claim_id": claim_ids[claim.order],
                        "passage_external_id": evidence.passage.id,
                        "support_type": evidence.relation,
                        "ranking_score": evidence.score,
                        "evidence_explanation": evidence.explanation,
                    }
                )
        if evidence_rows:
            self.client.table("claim_evidence").insert(evidence_rows).execute()
        if audit.handoff:
            self.client.table("handoff_briefs").insert(
                {
                    "audit_run_id": run_id,
                    "issue": audit.handoff.issue,
                    "established_facts": audit.handoff.established_points,
                    "relevant_authorities": audit.handoff.relevant_authorities,
                    "unresolved_questions": audit.handoff.unresolved_questions,
                    "review_status": audit.handoff.review_status,
                }
            ).execute()
        self.client.table("audit_events").insert(
            {
                "audit_run_id": run_id,
                "event_type": "complete",
                "event_payload": {
                    "engine_version": audit.engine_version,
                    "corpus_version": audit.corpus_version,
                },
            }
        ).execute()
        return audit

    def get(self, public_id: UUID) -> AuditDetail | None:
        response = (
            self.client.table("audit_runs")
            .select("result_payload")
            .eq("organisation_id", self.organisation_id)
            .eq("public_id", str(public_id))
            .gt("retention_expires_at", datetime.now(UTC).isoformat())
            .maybe_single()
            .execute()
        )
        if not response.data:
            return None
        return AuditDetail.model_validate(response.data["result_payload"])

    def list(self) -> list[AuditSummary]:
        response = (
            self.client.table("audit_runs")
            .select("result_payload")
            .eq("organisation_id", self.organisation_id)
            .order("created_at", desc=True)
            .gt("retention_expires_at", datetime.now(UTC).isoformat())
            .limit(100)
            .execute()
        )
        return [AuditSummary(**AuditDetail.model_validate(row["result_payload"]).model_dump()) for row in response.data]

    def find_cached(self, cache_key: str) -> AuditDetail | None:
        response = (
            self.client.table("audit_runs")
            .select("result_payload")
            .eq("organisation_id", self.organisation_id)
            .eq("audit_cache_key", cache_key)
            .eq("status", "complete")
            .gt("retention_expires_at", datetime.now(UTC).isoformat())
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return AuditDetail.model_validate(response.data[0]["result_payload"]) if response.data else None

    def delete(self, public_id: UUID) -> bool:
        response = (
            self.client.table("audit_runs")
            .delete()
            .eq("organisation_id", self.organisation_id)
            .eq("created_by", self.user_id)
            .eq("public_id", str(public_id))
            .execute()
        )
        return bool(response.data)


class SupabaseCorpusRefreshRepository:
    """Server-side snapshot persistence; never instantiated by the dashboard."""

    def __init__(self, settings: Settings, bearer_token: str) -> None:
        audit_repository = SupabaseAuditRepository(settings, bearer_token)
        self.client = audit_repository.client
        self.user_id = audit_repository.user_id
        self._row_ids: dict[UUID, int] = {}

    def create(self, run: RefreshRun) -> None:
        response = (
            self.client.table("corpus_refresh_runs")
            .insert(
                {
                    "public_id": str(run.public_id),
                    "requested_by": self.user_id,
                    "source_connector": run.source_connector,
                    "profile_version": run.profile_version,
                    "status": "running",
                    "requested_limit": run.requested_limit,
                    "started_at": (run.started_at or datetime.now(UTC)).isoformat(),
                }
            )
            .execute()
        )
        self._row_ids[run.public_id] = response.data[0]["id"]

    def finish(self, run: RefreshRun, corpus: ActiveCorpusRepository | None = None) -> None:
        row_id = self._row_ids.get(run.public_id)
        if row_id is None:
            lookup = self.client.table("corpus_refresh_runs").select("id").eq("public_id", str(run.public_id)).maybe_single().execute()
            if not lookup.data:
                return
            row_id = lookup.data["id"]
        if run.status == "complete" and corpus is not None:
            metadata = corpus.get_metadata()
            self.client.rpc(
                "activate_official_corpus_snapshot",
                {
                    "p_version": metadata.version,
                    "p_name": metadata.name,
                    "p_scope_statement": metadata.scope_statement,
                    "p_content_hash": metadata.content_hash,
                    "p_profile_version": metadata.profile_version,
                    "p_snapshot_created_at": (metadata.snapshot_created_at.isoformat() if metadata.snapshot_created_at else None),
                    "p_refresh_run_id": row_id,
                    "p_authorities": [authority.model_dump(mode="json") for authority in corpus.list_authorities()],
                },
            ).execute()
        self.client.table("corpus_refresh_runs").update(
            {
                "status": run.status,
                "accepted_documents": run.accepted_documents,
                "rejected_documents": run.rejected_documents,
                "accepted_passages": run.accepted_passages,
                "fallback_reason": run.fallback_reason,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "duration_ms": run.duration_ms,
            }
        ).eq("id", row_id).execute()

    def latest(self) -> RefreshRun | None:
        response = (
            self.client.table("corpus_refresh_runs")
            .select(
                "public_id,status,source_connector,profile_version,requested_limit,"
                "accepted_documents,rejected_documents,accepted_passages,fallback_reason,"
                "started_at,completed_at,duration_ms"
            )
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return RefreshRun.model_validate(response.data[0]) if response.data else None


class SupabaseGovernanceRepository(SupabaseAuditRepository):
    """Persists review overlays with the service secret after membership checks."""

    def persist_case_map(self, case_map: CaseMapDetail) -> CaseMapDetail:
        existing = (
            self.client.table("case_map_runs")
            .select("id")
            .eq("organisation_id", self.organisation_id)
            .eq("public_id", str(case_map.public_id))
            .maybe_single()
            .execute()
        )
        source: dict[str, int | None] = {"authority_id": None, "source_import_id": None}
        if case_map.source_provenance == "user_supplied":
            imported = (
                self.client.table("source_imports")
                .upsert(
                    {
                        "organisation_id": self.organisation_id,
                        "imported_by": self.user_id,
                        "filename": f"{case_map.case_name}.pdf",
                        "expected_citation": case_map.citation,
                        "normalised_citation_key": case_map.citation_key,
                        "stated_official_url": case_map.source_url,
                        "document_hash": case_map.document_hash,
                        "source_provenance": "user_supplied",
                        "extracted_paragraphs": [item.model_dump(mode="json") for item in case_map.source_paragraphs],
                        "warnings": ["User-supplied material is never treated as an official source."],
                    },
                    on_conflict="organisation_id,document_hash",
                )
                .execute()
            )
            source["source_import_id"] = imported.data[0]["id"]
        else:
            authority = (
                self.client.table("authorities")
                .select("id")
                .eq("normalised_citation_key", case_map.citation_key)
                .eq("document_hash", case_map.document_hash)
                .limit(1)
                .execute()
            )
            if not authority.data:
                raise RuntimeError("The Case Map source hash is not present in Supabase")
            source["authority_id"] = authority.data[0]["id"]

        payload = {
            "organisation_id": self.organisation_id,
            "created_by": self.user_id,
            "public_id": str(case_map.public_id),
            "normalised_citation_key": case_map.citation_key,
            "document_hash": case_map.document_hash,
            "schema_version": case_map.schema_version,
            "map_version": case_map.version,
            "model_version": case_map.model,
            "prompt_version": case_map.prompt_version,
            "annotator_version": case_map.annotator_version,
            "extractor_version": case_map.extractor_version,
            "status": case_map.status,
            "validation_errors": case_map.validation_errors,
            "reviewed_by": str(case_map.reviewer_id) if case_map.reviewer_id else None,
            "reviewed_at": case_map.reviewed_at.isoformat() if case_map.reviewed_at else None,
            **source,
        }
        if existing.data:
            run_id = existing.data["id"]
            self.client.table("case_map_runs").update(payload).eq("id", run_id).execute()
            if case_map.status == "approved":
                self.client.table("case_map_annotations").update(
                    {
                        "review_status": "approved",
                        "human_verified": True,
                        "verified_by": self.user_id,
                        "extraction_method": "hybrid",
                    }
                ).eq("case_map_run_id", run_id).execute()
                self.client.table("case_map_review_events").insert(
                    {
                        "case_map_run_id": run_id,
                        "actor_id": self.user_id,
                        "event_type": "approve",
                        "new_value": {"version": case_map.version, "status": case_map.status},
                    }
                ).execute()
        else:
            created = self.client.table("case_map_runs").insert(payload).execute()
            run_id = created.data[0]["id"]
            annotation_rows = [
                {
                    "case_map_run_id": run_id,
                    "annotation_type": annotation.annotation_type,
                    "proposition_code": annotation.proposition_code,
                    "statement": annotation.statement,
                    "paragraph_labels": annotation.paragraph_labels,
                    "supporting_quote": annotation.supporting_quote,
                    "modality": annotation.modality,
                    "limitations": annotation.limitations,
                    "applicability_factors": annotation.applicability_factors,
                    "model_confidence": annotation.model_confidence,
                    "validation_status": annotation.validation_status,
                    "validation_messages": annotation.validation_messages,
                    "review_status": annotation.review_status,
                    "field_tier": annotation.provenance.tier if annotation.provenance else "C",
                    "extraction_method": annotation.provenance.extraction_method if annotation.provenance else "model",
                    "human_verified": annotation.provenance.human_verified if annotation.provenance else False,
                    "verified_by": (
                        str(annotation.provenance.verified_by)
                        if annotation.provenance and annotation.provenance.verified_by
                        else None
                    ),
                    "supporting_evidence": (
                        annotation.provenance.supporting_evidence
                        if annotation.provenance
                        else annotation.paragraph_labels
                    ),
                    "field_version": annotation.provenance.version if annotation.provenance else 1,
                }
                for annotation in case_map.annotations
            ]
            if annotation_rows:
                self.client.table("case_map_annotations").insert(annotation_rows).execute()
            self.client.table("case_map_review_events").insert(
                {
                    "case_map_run_id": run_id,
                    "actor_id": self.user_id,
                    "event_type": "approve" if case_map.status == "approved" else "edit",
                    "new_value": {"version": case_map.version, "status": case_map.status},
                }
            ).execute()
        supersedes = next((event.get("supersedes") for event in case_map.revision_history if event.get("supersedes")), None)
        if supersedes:
            self.client.table("case_map_runs").update({"status": "superseded"}).eq("organisation_id", self.organisation_id).eq(
                "public_id", supersedes
            ).execute()
        return case_map

    def persist_feedback(self, feedback: PractitionerFeedback) -> PractitionerFeedback:
        run = (
            self.client.table("audit_runs")
            .select("id")
            .eq("organisation_id", self.organisation_id)
            .eq("public_id", str(feedback.audit_public_id))
            .maybe_single()
            .execute()
        )
        if not run.data:
            raise PermissionError("Audit not found in the signed-in organisation")
        claim = (
            self.client.table("audit_claims")
            .select("id")
            .eq("audit_run_id", run.data["id"])
            .eq("claim_order", feedback.claim_order)
            .maybe_single()
            .execute()
        )
        if not claim.data:
            raise LookupError("Audit claim not found")
        self.client.table("practitioner_feedback").insert(
            {
                "public_id": str(feedback.public_id),
                "organisation_id": self.organisation_id,
                "audit_claim_id": claim.data["id"],
                "submitted_by": self.user_id,
                "category": feedback.category,
                "explanation": feedback.explanation,
                "proposed_citation": feedback.proposed_citation,
                "proposed_paragraph": feedback.proposed_paragraph,
                "proposed_correction": feedback.proposed_correction,
                "status": feedback.status,
            }
        ).execute()
        return feedback.model_copy(update={"organisation_id": self.organisation_id, "submitted_by": UUID(self.user_id)})

    def persist_feedback_resolution(self, feedback: PractitionerFeedback) -> PractitionerFeedback:
        self.client.table("practitioner_feedback").update(
            {
                "status": feedback.status,
                "resolution_note": feedback.resolution_note,
                "resolved_by": self.user_id,
                "resolved_at": feedback.resolved_at.isoformat() if feedback.resolved_at else datetime.now(UTC).isoformat(),
            }
        ).eq("organisation_id", self.organisation_id).eq("public_id", str(feedback.public_id)).execute()
        return feedback.model_copy(update={"organisation_id": self.organisation_id, "resolved_by": UUID(self.user_id)})

    def persist_legal_currency_record(self, submission: LegalCurrencyRecordSubmission) -> LegalCurrencyRecord:
        active_corpus = self.client.table("authority_corpora").select("id").eq("is_active", True).maybe_single().execute()
        if not active_corpus.data:
            raise RuntimeError("No active official corpus is available for a currency record")

        def authority_id(citation: str) -> int:
            result = (
                self.client.table("authorities")
                .select("id")
                .eq("corpus_id", active_corpus.data["id"])
                .eq("normalised_citation_key", normalise_citation(citation))
                .maybe_single()
                .execute()
            )
            if not result.data:
                raise LookupError(f"{citation} is not present in the active official snapshot")
            return result.data["id"]

        target_authority_id = authority_id(submission.authority_citation)
        source_authority_id = authority_id(submission.source_citation) if submission.source_citation else None
        reviewed_at = datetime.now(UTC)
        self.client.table("legal_currency_records").insert(
            {
                "organisation_id": self.organisation_id,
                "authority_id": target_authority_id,
                "record_type": submission.record_type,
                "treatment": submission.treatment,
                "source_authority_id": source_authority_id,
                "statute_reference": submission.statute_reference,
                "effective_date": submission.effective_date.isoformat() if submission.effective_date else None,
                "note": submission.note,
                "review_status": "approved",
                "reviewed_by": self.user_id,
                "reviewed_at": reviewed_at.isoformat(),
            }
        ).execute()
        return LegalCurrencyRecord(
            **submission.model_dump(),
            review_status="approved",
            reviewed_by=UUID(self.user_id),
            reviewed_at=reviewed_at,
        )

    def currency_context(self) -> tuple[dict[str, str], str]:
        records = (
            self.client.table("legal_currency_records")
            .select("authority_id,treatment,reviewed_at")
            .eq("organisation_id", self.organisation_id)
            .eq("review_status", "approved")
            .execute()
            .data
        )
        if not records:
            return {}, "currency-none"
        authority_ids = list({item["authority_id"] for item in records})
        authorities = self.client.table("authorities").select("id,normalised_citation_key").in_("id", authority_ids).execute().data
        citation_by_id = {item["id"]: item["normalised_citation_key"] for item in authorities}
        statuses: dict[str, str] = {}
        for record in records:
            citation_key = citation_by_id.get(record["authority_id"])
            if not citation_key:
                continue
            status = "negative_treatment" if record["treatment"] in {"limits", "overrules", "supersedes", "amends"} else "current_reviewed"
            # A negative record must always win over a later positive review.
            if statuses.get(citation_key) != "negative_treatment":
                statuses[citation_key] = status
        material = [
            {
                "citation_key": citation_by_id.get(item["authority_id"]),
                "treatment": item["treatment"],
                "reviewed_at": item["reviewed_at"],
            }
            for item in records
            if citation_by_id.get(item["authority_id"])
        ]
        version = (
            "currency-"
            + hashlib.sha256(
                json.dumps(sorted(material, key=lambda item: json.dumps(item, sort_keys=True)), sort_keys=True).encode("utf-8")
            ).hexdigest()[:16]
        )
        return statuses, version
