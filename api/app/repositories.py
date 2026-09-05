from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.config import Settings
from app.models import AuditDetail, AuditSummary


class AuditRepository(Protocol):
    def save(self, audit: AuditDetail) -> AuditDetail: ...

    def get(self, public_id: UUID) -> AuditDetail | None: ...

    def list(self) -> list[AuditSummary]: ...


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


class SupabaseAuditRepository:
    """Server-side repository. The secret key must never be used by the dashboard."""

    def __init__(self, settings: Settings, bearer_token: str) -> None:
        from supabase import create_client

        if not settings.supabase_secret_key:
            raise RuntimeError("Supabase server-side secret is not configured")
        self.client = create_client(settings.supabase_url, settings.supabase_secret_key)
        auth_response = self.client.auth.get_user(bearer_token)
        if not auth_response.user:
            raise PermissionError("Invalid Supabase bearer token")
        self.user_id = str(auth_response.user.id)
        membership = (
            self.client.table("organisation_members")
            .select("organisation_id")
            .eq("user_id", self.user_id)
            .limit(1)
            .execute()
        )
        if not membership.data:
            raise PermissionError("The signed-in user has no ProofMark organisation")
        self.organisation_id = membership.data[0]["organisation_id"]

    def save(self, audit: AuditDetail) -> AuditDetail:
        run_payload = {
            "organisation_id": self.organisation_id,
            "created_by": self.user_id,
            "public_id": str(audit.public_id),
            "input_text": audit.input_text,
            "status": "complete",
            "corpus_version": audit.corpus_version,
            "engine_version": audit.engine_version,
            "parser_mode": audit.parser_used,
            "processing_duration_ms": audit.processing_duration_ms,
            "summary_metrics": audit.metrics.model_dump(),
            "summary_counts": audit.summary_counts,
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
                }
            )
        claim_response = self.client.table("audit_claims").insert(claim_rows).execute()
        claim_ids = {
            row["claim_order"]: row["id"]
            for row in claim_response.data
        }
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
            .limit(100)
            .execute()
        )
        return [
            AuditSummary(**AuditDetail.model_validate(row["result_payload"]).model_dump())
            for row in response.data
        ]
