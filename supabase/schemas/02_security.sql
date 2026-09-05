alter table public.organisations enable row level security;
alter table public.organisation_members enable row level security;
alter table public.authority_corpora enable row level security;
alter table public.authorities enable row level security;
alter table public.authority_passages enable row level security;
alter table public.citation_registry_checks enable row level security;
alter table public.audit_runs enable row level security;
alter table public.audit_claims enable row level security;
alter table public.claim_evidence enable row level security;
alter table public.handoff_briefs enable row level security;
alter table public.audit_events enable row level security;
alter table public.benchmark_runs enable row level security;

revoke all on table public.organisations from anon, authenticated;
revoke all on table public.organisation_members from anon, authenticated;
revoke all on table public.authority_corpora from anon, authenticated;
revoke all on table public.authorities from anon, authenticated;
revoke all on table public.authority_passages from anon, authenticated;
revoke all on table public.citation_registry_checks from anon, authenticated;
revoke all on table public.audit_runs from anon, authenticated;
revoke all on table public.audit_claims from anon, authenticated;
revoke all on table public.claim_evidence from anon, authenticated;
revoke all on table public.handoff_briefs from anon, authenticated;
revoke all on table public.audit_events from anon, authenticated;
revoke all on table public.benchmark_runs from anon, authenticated;

grant select on table public.organisations to authenticated;
grant select on table public.organisation_members to authenticated;
grant select on table public.authority_corpora to authenticated;
grant select on table public.authorities to authenticated;
grant select on table public.authority_passages to authenticated;
grant select on table public.citation_registry_checks to authenticated;
grant select on table public.audit_runs to authenticated;
grant select on table public.audit_claims to authenticated;
grant select on table public.claim_evidence to authenticated;
grant select on table public.handoff_briefs to authenticated;
grant select on table public.audit_events to authenticated;
grant select on table public.benchmark_runs to authenticated;

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
