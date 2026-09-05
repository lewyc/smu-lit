create extension if not exists pgcrypto with schema extensions;

create table public.organisations (
  id bigint generated always as identity primary key,
  name text not null,
  slug text not null unique check (slug = lower(slug)),
  created_at timestamptz not null default now()
);

create table public.organisation_members (
  id bigint generated always as identity primary key,
  organisation_id bigint not null references public.organisations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('owner', 'reviewer', 'member')),
  created_at timestamptz not null default now(),
  unique (organisation_id, user_id)
);

create table public.authority_corpora (
  id bigint generated always as identity primary key,
  version text not null unique,
  jurisdiction text not null,
  name text not null,
  scope_statement text not null,
  content_hash text not null check (length(content_hash) = 64),
  source_status text not null check (source_status in ('research_verified', 'verification_required')),
  is_active boolean not null default false,
  created_at timestamptz not null default now()
);

create unique index authority_corpora_one_active_idx
  on public.authority_corpora (is_active) where is_active;

create table public.authorities (
  id bigint generated always as identity primary key,
  corpus_id bigint not null references public.authority_corpora(id) on delete restrict,
  canonical_citation text not null,
  normalised_citation_key text not null,
  case_name text not null,
  court text not null,
  decision_date date not null,
  official_url text not null check (official_url like 'https://%'),
  source_status text not null check (source_status in ('research_verified', 'verification_required')),
  created_at timestamptz not null default now(),
  unique (corpus_id, normalised_citation_key)
);

create table public.authority_passages (
  id bigint generated always as identity primary key,
  authority_id bigint not null references public.authorities(id) on delete restrict,
  external_id text not null unique,
  paragraph_label text not null,
  passage_text text not null,
  supported_propositions text[] not null default '{}',
  limitations text[] not null default '{}',
  search_vector tsvector generated always as (
    to_tsvector('english', coalesce(passage_text, '') || ' ' || coalesce(paragraph_label, ''))
  ) stored,
  created_at timestamptz not null default now(),
  unique (authority_id, paragraph_label)
);

create table public.citation_registry_checks (
  id bigint generated always as identity primary key,
  corpus_id bigint not null references public.authority_corpora(id) on delete restrict,
  citation_string text not null,
  normalised_citation_key text not null,
  authority_exists boolean not null,
  official_source_url text not null check (official_source_url like 'https://%'),
  checker text not null,
  verification_note text,
  checked_at timestamptz not null,
  created_at timestamptz not null default now(),
  unique (corpus_id, normalised_citation_key, checked_at)
);

create table public.audit_runs (
  id bigint generated always as identity primary key,
  public_id uuid not null default gen_random_uuid() unique,
  organisation_id bigint not null references public.organisations(id) on delete restrict,
  created_by uuid not null references auth.users(id) on delete restrict,
  input_text text not null check (char_length(input_text) between 1 and 20000),
  status text not null check (status in ('queued', 'running', 'complete', 'failed')),
  corpus_version text not null,
  engine_version text not null,
  parser_mode text not null check (parser_mode in ('local', 'gemini')),
  processing_duration_ms numeric(12, 3) check (processing_duration_ms >= 0),
  summary_metrics jsonb not null default '{}'::jsonb,
  summary_counts jsonb not null default '{}'::jsonb,
  result_payload jsonb,
  failure_code text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  check (status <> 'complete' or completed_at is not null),
  check (status <> 'failed' or failure_code is not null)
);

create table public.audit_claims (
  id bigint generated always as identity primary key,
  audit_run_id bigint not null references public.audit_runs(id) on delete cascade,
  claim_order bigint not null check (claim_order > 0),
  claim_text text not null,
  citation text,
  pinpoint text,
  proposition_code text not null,
  parser_confidence numeric(4, 3) not null check (parser_confidence between 0 and 1),
  parser_used text not null check (parser_used in ('local', 'gemini')),
  verdict text not null check (
    verdict in ('verified', 'context_review', 'unsupported', 'likely_fabricated', 'unverified', 'out_of_scope')
  ),
  rationale text not null,
  missing_evidence text,
  escalation_required boolean not null,
  created_at timestamptz not null default now(),
  unique (audit_run_id, claim_order)
);

create table public.claim_evidence (
  id bigint generated always as identity primary key,
  audit_claim_id bigint not null references public.audit_claims(id) on delete cascade,
  passage_external_id text not null references public.authority_passages(external_id) on delete restrict,
  support_type text not null check (support_type in ('supports', 'limits', 'contradicts', 'unresolved')),
  ranking_score numeric(6, 5) not null check (ranking_score between 0 and 1),
  evidence_explanation text not null,
  created_at timestamptz not null default now(),
  unique (audit_claim_id, passage_external_id, support_type)
);

create table public.handoff_briefs (
  id bigint generated always as identity primary key,
  audit_run_id bigint not null unique references public.audit_runs(id) on delete cascade,
  issue text not null,
  established_facts text[] not null default '{}',
  relevant_authorities text[] not null default '{}',
  unresolved_questions text[] not null default '{}',
  review_status text not null check (review_status in ('lawyer_review_required', 'ready', 'reviewed')),
  reviewed_by uuid references auth.users(id) on delete restrict,
  reviewed_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.audit_events (
  id bigint generated always as identity primary key,
  audit_run_id bigint not null references public.audit_runs(id) on delete cascade,
  event_type text not null check (event_type in ('queued', 'running', 'complete', 'failed')),
  event_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table public.benchmark_runs (
  id bigint generated always as identity primary key,
  organisation_id bigint not null references public.organisations(id) on delete restrict,
  created_by uuid not null references auth.users(id) on delete restrict,
  fixture_count bigint not null check (fixture_count > 0),
  correct_count bigint not null check (correct_count between 0 and fixture_count),
  verdict_accuracy numeric(6, 3) not null check (verdict_accuracy between 0 and 100),
  p50_latency_ms numeric(12, 3) not null check (p50_latency_ms >= 0),
  p95_latency_ms numeric(12, 3) not null check (p95_latency_ms >= 0),
  cache_hit_rate numeric(6, 3) check (cache_hit_rate between 0 and 100),
  engine_version text not null,
  corpus_version text not null,
  created_at timestamptz not null default now()
);

create index organisation_members_user_id_idx on public.organisation_members (user_id);
create index organisation_members_organisation_id_idx on public.organisation_members (organisation_id);
create index authorities_corpus_id_idx on public.authorities (corpus_id);
create index authority_passages_authority_id_idx on public.authority_passages (authority_id);
create index authority_passages_search_idx on public.authority_passages using gin (search_vector);
create index citation_registry_checks_corpus_id_idx on public.citation_registry_checks (corpus_id);
create index audit_runs_created_by_idx on public.audit_runs (created_by);
create index audit_runs_org_created_idx on public.audit_runs (organisation_id, created_at desc);
create index audit_runs_active_idx on public.audit_runs (created_at)
  where status in ('queued', 'running');
create index audit_claims_run_order_idx on public.audit_claims (audit_run_id, claim_order);
create index claim_evidence_claim_idx on public.claim_evidence (audit_claim_id);
create index claim_evidence_passage_idx on public.claim_evidence (passage_external_id);
create index handoff_briefs_reviewed_by_idx on public.handoff_briefs (reviewed_by)
  where reviewed_by is not null;
create index audit_events_run_created_idx on public.audit_events (audit_run_id, created_at);
create index benchmark_runs_created_by_idx on public.benchmark_runs (created_by);
create index benchmark_runs_org_created_idx on public.benchmark_runs (organisation_id, created_at desc);

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
