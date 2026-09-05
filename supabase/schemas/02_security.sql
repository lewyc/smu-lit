alter table public.organisations enable row level security;
alter table public.organisation_members enable row level security;
alter table public.authority_corpora enable row level security;
alter table public.authorities enable row level security;
alter table public.authority_passages enable row level security;
alter table public.citation_registry_checks enable row level security;
alter table public.corpus_refresh_runs enable row level security;
alter table public.audit_runs enable row level security;
alter table public.audit_claims enable row level security;
alter table public.claim_evidence enable row level security;
alter table public.handoff_briefs enable row level security;
alter table public.audit_events enable row level security;
alter table public.benchmark_runs enable row level security;
alter table public.source_imports enable row level security;
alter table public.case_map_runs enable row level security;
alter table public.case_map_annotations enable row level security;
alter table public.case_map_review_events enable row level security;
alter table public.authority_assessments enable row level security;
alter table public.authority_relationships enable row level security;
alter table public.legal_currency_records enable row level security;
alter table public.practitioner_feedback enable row level security;
alter table public.reference_sources enable row level security;

revoke all on table public.organisations from anon, authenticated;
revoke all on table public.organisation_members from anon, authenticated;
revoke all on table public.authority_corpora from anon, authenticated;
revoke all on table public.authorities from anon, authenticated;
revoke all on table public.authority_passages from anon, authenticated;
revoke all on table public.citation_registry_checks from anon, authenticated;
revoke all on table public.corpus_refresh_runs from anon, authenticated;
revoke all on table public.audit_runs from anon, authenticated;
revoke all on table public.audit_claims from anon, authenticated;
revoke all on table public.claim_evidence from anon, authenticated;
revoke all on table public.handoff_briefs from anon, authenticated;
revoke all on table public.audit_events from anon, authenticated;
revoke all on table public.benchmark_runs from anon, authenticated;
revoke all on table public.source_imports from anon, authenticated;
revoke all on table public.case_map_runs from anon, authenticated;
revoke all on table public.case_map_annotations from anon, authenticated;
revoke all on table public.case_map_review_events from anon, authenticated;
revoke all on table public.authority_assessments from anon, authenticated;
revoke all on table public.authority_relationships from anon, authenticated;
revoke all on table public.legal_currency_records from anon, authenticated;
revoke all on table public.practitioner_feedback from anon, authenticated;
revoke all on table public.reference_sources from anon, authenticated;

grant select on table public.organisations to authenticated;
grant select on table public.organisation_members to authenticated;
grant select on table public.authority_corpora to authenticated;
grant select on table public.authorities to authenticated;
grant select on table public.authority_passages to authenticated;
grant select on table public.citation_registry_checks to authenticated;
grant select on table public.corpus_refresh_runs to authenticated;
grant select on table public.audit_runs to authenticated;
grant select on table public.audit_claims to authenticated;
grant select on table public.claim_evidence to authenticated;
grant select on table public.handoff_briefs to authenticated;
grant select on table public.audit_events to authenticated;
grant select on table public.benchmark_runs to authenticated;
grant select on table public.source_imports to authenticated;
grant select on table public.case_map_runs to authenticated;
grant select on table public.case_map_annotations to authenticated;
grant select on table public.case_map_review_events to authenticated;
grant select on table public.authority_assessments to authenticated;
grant select on table public.authority_relationships to authenticated;
grant select on table public.legal_currency_records to authenticated;
grant select on table public.practitioner_feedback to authenticated;
grant select on table public.reference_sources to authenticated;

grant select, insert, update, delete on all tables in schema public to service_role;
grant usage, select on all sequences in schema public to service_role;

create policy organisations_member_read on public.organisations
  for select to authenticated
  using (
    exists (
      select 1 from public.organisation_members membership
      where membership.organisation_id = organisations.id
        and membership.user_id = (select auth.uid())
    )
  );

create policy organisation_members_self_read on public.organisation_members
  for select to authenticated
  using (user_id = (select auth.uid()));

create policy authority_corpora_authenticated_read on public.authority_corpora
  for select to authenticated using (true);

create policy authorities_authenticated_read on public.authorities
  for select to authenticated using (true);

create policy authority_passages_authenticated_read on public.authority_passages
  for select to authenticated using (true);

create policy citation_checks_authenticated_read on public.citation_registry_checks
  for select to authenticated using (true);

create policy corpus_refresh_runs_authenticated_read on public.corpus_refresh_runs
  for select to authenticated using (true);

create policy audit_runs_member_read on public.audit_runs
  for select to authenticated
  using (
    exists (
      select 1 from public.organisation_members membership
      where membership.organisation_id = audit_runs.organisation_id
        and membership.user_id = (select auth.uid())
    )
  );

create policy audit_claims_member_read on public.audit_claims
  for select to authenticated
  using (
    exists (
      select 1
      from public.audit_runs run
      join public.organisation_members membership
        on membership.organisation_id = run.organisation_id
      where run.id = audit_claims.audit_run_id
        and membership.user_id = (select auth.uid())
    )
  );

create policy claim_evidence_member_read on public.claim_evidence
  for select to authenticated
  using (
    exists (
      select 1
      from public.audit_claims claim
      join public.audit_runs run on run.id = claim.audit_run_id
      join public.organisation_members membership
        on membership.organisation_id = run.organisation_id
      where claim.id = claim_evidence.audit_claim_id
        and membership.user_id = (select auth.uid())
    )
  );

create policy handoff_briefs_member_read on public.handoff_briefs
  for select to authenticated
  using (
    exists (
      select 1
      from public.audit_runs run
      join public.organisation_members membership
        on membership.organisation_id = run.organisation_id
      where run.id = handoff_briefs.audit_run_id
        and membership.user_id = (select auth.uid())
    )
  );

create policy audit_events_member_read on public.audit_events
  for select to authenticated
  using (
    exists (
      select 1
      from public.audit_runs run
      join public.organisation_members membership
        on membership.organisation_id = run.organisation_id
      where run.id = audit_events.audit_run_id
        and membership.user_id = (select auth.uid())
    )
  );

create policy benchmark_runs_member_read on public.benchmark_runs
  for select to authenticated
  using (
    exists (
      select 1 from public.organisation_members membership
      where membership.organisation_id = benchmark_runs.organisation_id
        and membership.user_id = (select auth.uid())
    )
  );

create policy source_imports_member_read on public.source_imports
  for select to authenticated using (
    exists (
      select 1 from public.organisation_members membership
      where membership.organisation_id = source_imports.organisation_id
        and membership.user_id = (select auth.uid())
    )
  );

create policy case_map_runs_member_read on public.case_map_runs
  for select to authenticated using (
    exists (
      select 1 from public.organisation_members membership
      where membership.organisation_id = case_map_runs.organisation_id
        and membership.user_id = (select auth.uid())
    )
  );

create policy case_map_annotations_member_read on public.case_map_annotations
  for select to authenticated using (
    exists (
      select 1 from public.case_map_runs map
      join public.organisation_members membership on membership.organisation_id = map.organisation_id
      where map.id = case_map_annotations.case_map_run_id
        and membership.user_id = (select auth.uid())
    )
  );

create policy case_map_review_events_member_read on public.case_map_review_events
  for select to authenticated using (
    exists (
      select 1 from public.case_map_runs map
      join public.organisation_members membership on membership.organisation_id = map.organisation_id
      where map.id = case_map_review_events.case_map_run_id
        and membership.user_id = (select auth.uid())
    )
  );

create policy authority_assessments_member_read on public.authority_assessments
  for select to authenticated using (
    exists (
      select 1 from public.organisation_members membership
      where membership.organisation_id = authority_assessments.organisation_id
        and membership.user_id = (select auth.uid())
    )
  );

create policy authority_relationships_member_read on public.authority_relationships
  for select to authenticated using (
    exists (
      select 1 from public.organisation_members membership
      where membership.organisation_id = authority_relationships.organisation_id
        and membership.user_id = (select auth.uid())
    )
  );

create policy legal_currency_records_member_read on public.legal_currency_records
  for select to authenticated
  using (
    exists (
      select 1 from public.organisation_members membership
      where membership.organisation_id = legal_currency_records.organisation_id
        and membership.user_id = (select auth.uid())
    )
  );

create policy practitioner_feedback_member_read on public.practitioner_feedback
  for select to authenticated using (
    exists (
      select 1 from public.organisation_members membership
      where membership.organisation_id = practitioner_feedback.organisation_id
        and membership.user_id = (select auth.uid())
    )
  );

create policy reference_sources_member_read on public.reference_sources
  for select to authenticated using (
    exists (
      select 1 from public.organisation_members membership
      where membership.organisation_id = reference_sources.organisation_id
        and membership.user_id = (select auth.uid())
    )
  );

create or replace function public.prevent_case_map_history_mutation()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
  raise exception 'Case Map review events are append-only';
end;
$$;

create trigger case_map_review_events_append_only
before update or delete on public.case_map_review_events
for each row execute function public.prevent_case_map_history_mutation();
