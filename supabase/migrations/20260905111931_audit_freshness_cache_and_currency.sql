-- Source-versioned audit caching, reproducible re-audits, and reviewed legal-currency records.

alter table public.audit_runs
  add column parser_version text not null default 'local-claims.1',
  add column audit_cache_key text,
  add column cache_status text not null default 'miss',
  add column source_checked_at timestamptz,
  add column currency_registry_version text not null default 'currency-none',
  add column retention_expires_at timestamptz not null default (now() + interval '30 days'),
  add column re_audited_from_id bigint references public.audit_runs(id) on delete set null,
  add constraint audit_runs_cache_status_check check (cache_status in ('hit', 'miss', 'bypassed'));

create index audit_runs_cache_lookup_idx
  on public.audit_runs (organisation_id, audit_cache_key, created_at desc)
  where status = 'complete' and audit_cache_key is not null;
create index audit_runs_retention_expiry_idx
  on public.audit_runs (retention_expires_at)
  where retention_expires_at is not null;
create index audit_runs_re_audited_from_id_idx
  on public.audit_runs (re_audited_from_id)
  where re_audited_from_id is not null;

create table public.legal_currency_records (
  id bigint generated always as identity primary key,
  organisation_id bigint not null references public.organisations(id) on delete restrict,
  authority_id bigint not null references public.authorities(id) on delete restrict,
  record_type text not null check (record_type in ('later_treatment', 'statutory_amendment', 'supersession')),
  treatment text not null check (treatment in ('follows', 'distinguishes', 'limits', 'overrules', 'supersedes', 'amends')),
  source_authority_id bigint references public.authorities(id) on delete restrict,
  statute_reference text,
  effective_date date,
  note text,
  review_status text not null default 'draft' check (review_status in ('draft', 'approved', 'rejected', 'superseded')),
  reviewed_by uuid references auth.users(id) on delete restrict,
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  check (
    (record_type = 'statutory_amendment' and statute_reference is not null)
    or (record_type <> 'statutory_amendment' and source_authority_id is not null)
  )
);

create index legal_currency_records_org_authority_status_idx
  on public.legal_currency_records (organisation_id, authority_id, review_status);
create index legal_currency_records_source_authority_idx
  on public.legal_currency_records (source_authority_id)
  where source_authority_id is not null;
create index legal_currency_records_reviewed_by_idx
  on public.legal_currency_records (reviewed_by)
  where reviewed_by is not null;

alter table public.legal_currency_records enable row level security;
revoke all on table public.legal_currency_records from anon, authenticated;
grant select on table public.legal_currency_records to authenticated;
grant select, insert, update, delete on table public.legal_currency_records to service_role;
grant usage, select on sequence public.legal_currency_records_id_seq to service_role;

create policy legal_currency_records_member_read on public.legal_currency_records
  for select to authenticated
  using (
    exists (
      select 1 from public.organisation_members membership
      where membership.organisation_id = legal_currency_records.organisation_id
        and membership.user_id = (select auth.uid())
    )
  );
