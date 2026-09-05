-- Hand-authored from the declarative schema because the Supabase CLI was not
-- available in the hackathon workspace. Review/apply after earlier migrations.

alter table public.case_map_annotations
  add column if not exists field_tier text not null default 'C'
    check (field_tier in ('A', 'B', 'C')),
  add column if not exists extraction_method text not null default 'model'
    check (extraction_method in ('deterministic', 'rule_based', 'model', 'human', 'hybrid')),
  add column if not exists human_verified boolean not null default false,
  add column if not exists verified_by uuid references auth.users(id) on delete restrict,
  add column if not exists supporting_evidence text[] not null default '{}',
  add column if not exists field_version bigint not null default 1
    check (field_version > 0),
  add column if not exists superseded_by_id bigint references public.case_map_annotations(id) on delete restrict;

create table if not exists public.case_map_field_dependencies (
  id bigint generated always as identity primary key,
  audit_claim_id bigint not null references public.audit_claims(id) on delete restrict,
  case_map_annotation_id bigint not null references public.case_map_annotations(id) on delete restrict,
  case_map_version bigint not null check (case_map_version > 0),
  consumed_for text not null check (consumed_for in (
    'proposition_support', 'authority_role', 'modality', 'limitation', 'applicability'
  )),
  created_at timestamptz not null default now(),
  unique (audit_claim_id, case_map_annotation_id, case_map_version, consumed_for)
);

create index if not exists case_map_annotations_verified_by_idx
  on public.case_map_annotations (verified_by) where verified_by is not null;
create index if not exists case_map_annotations_superseded_by_idx
  on public.case_map_annotations (superseded_by_id) where superseded_by_id is not null;
create index if not exists case_map_field_dependencies_claim_idx
  on public.case_map_field_dependencies (audit_claim_id);
create index if not exists case_map_field_dependencies_annotation_idx
  on public.case_map_field_dependencies (case_map_annotation_id, case_map_version);

alter table public.case_map_field_dependencies enable row level security;

revoke all on table public.case_map_field_dependencies from anon, authenticated;
grant select on table public.case_map_field_dependencies to authenticated;
grant select, insert, update, delete on table public.case_map_field_dependencies to service_role;
grant usage, select on sequence public.case_map_field_dependencies_id_seq to service_role;

create policy case_map_field_dependencies_member_read
  on public.case_map_field_dependencies
  for select to authenticated using (
    exists (
      select 1
      from public.audit_claims claim
      join public.audit_runs run on run.id = claim.audit_run_id
      join public.case_map_annotations annotation
        on annotation.id = case_map_field_dependencies.case_map_annotation_id
      join public.case_map_runs map on map.id = annotation.case_map_run_id
      join public.organisation_members membership on membership.organisation_id = run.organisation_id
      where claim.id = case_map_field_dependencies.audit_claim_id
        and map.organisation_id = run.organisation_id
        and membership.user_id = (select auth.uid())
    )
  );
