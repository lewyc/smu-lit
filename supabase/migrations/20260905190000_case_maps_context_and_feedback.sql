alter table public.audit_runs
  add column audit_mode text not null default 'citation_only' check (audit_mode in ('citation_only', 'full')),
  add column original_question text check (original_question is null or char_length(original_question) <= 5000),
  add column facts text check (facts is null or char_length(facts) <= 10000),
  add column module_scores jsonb not null default '{}'::jsonb,
  add column evaluation_provenance jsonb not null default '{}'::jsonb;

create table public.source_imports (
  id bigint generated always as identity primary key,
  public_id uuid not null default gen_random_uuid() unique,
  organisation_id bigint not null references public.organisations(id) on delete restrict,
  imported_by uuid not null references auth.users(id) on delete restrict,
  filename text not null,
  expected_citation text not null,
  normalised_citation_key text not null,
  stated_official_url text check (stated_official_url is null or stated_official_url like 'https://%'),
  document_hash text not null check (length(document_hash) = 64),
  source_provenance text not null default 'user_supplied' check (source_provenance = 'user_supplied'),
  extracted_paragraphs jsonb not null default '[]'::jsonb,
  warnings text[] not null default '{}',
  created_at timestamptz not null default now(),
  unique (organisation_id, document_hash)
);

create table public.case_map_runs (
  id bigint generated always as identity primary key,
  public_id uuid not null default gen_random_uuid() unique,
  organisation_id bigint not null references public.organisations(id) on delete restrict,
  authority_id bigint references public.authorities(id) on delete restrict,
  source_import_id bigint references public.source_imports(id) on delete restrict,
  created_by uuid not null references auth.users(id) on delete restrict,
  normalised_citation_key text not null,
  document_hash text not null check (length(document_hash) = 64),
  schema_version text not null,
  map_version bigint not null default 1 check (map_version > 0),
  model_version text not null,
  prompt_version text not null,
  annotator_version text not null,
  extractor_version text,
  status text not null check (status in ('queued', 'running', 'draft', 'approved', 'rejected', 'stale', 'failed')),
  validation_errors jsonb not null default '[]'::jsonb,
  processing_duration_ms numeric(12, 3) check (processing_duration_ms is null or processing_duration_ms >= 0),
  reviewed_by uuid references auth.users(id) on delete restrict,
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check ((authority_id is not null)::int + (source_import_id is not null)::int = 1),
  unique (organisation_id, normalised_citation_key, document_hash, schema_version, map_version)
);

create table public.case_map_annotations (
  id bigint generated always as identity primary key,
  public_id uuid not null default gen_random_uuid() unique,
  case_map_run_id bigint not null references public.case_map_runs(id) on delete restrict,
  annotation_type text not null check (annotation_type in (
    'ratio_candidate', 'holding', 'obiter_candidate', 'party_submission',
    'factual_finding', 'procedural_history', 'disposition'
  )),
  proposition_code text,
  statement text not null,
  paragraph_labels text[] not null check (cardinality(paragraph_labels) > 0),
  supporting_quote text not null check (char_length(supporting_quote) between 1 and 800),
  modality text not null check (modality in ('mandatory', 'qualified', 'permissive', 'descriptive')),
  limitations text[] not null default '{}',
  applicability_factors text[] not null default '{}',
  model_confidence numeric(4, 3) not null check (model_confidence between 0 and 1),
  validation_status text not null check (validation_status in ('valid', 'warning', 'invalid')),
  validation_messages text[] not null default '{}',
  review_status text not null default 'draft' check (review_status in ('draft', 'approved', 'rejected', 'superseded')),
  created_at timestamptz not null default now()
);

create table public.case_map_review_events (
  id bigint generated always as identity primary key,
  case_map_run_id bigint not null references public.case_map_runs(id) on delete restrict,
  annotation_id bigint references public.case_map_annotations(id) on delete restrict,
  actor_id uuid references auth.users(id) on delete restrict,
  event_type text not null check (event_type in ('edit', 'approve', 'reject', 'supersede', 'feedback_accepted')),
  previous_value jsonb,
  new_value jsonb,
  reason text,
  created_at timestamptz not null default now()
);

create table public.authority_assessments (
  id bigint generated always as identity primary key,
  organisation_id bigint not null references public.organisations(id) on delete restrict,
  authority_id bigint not null references public.authorities(id) on delete restrict,
  jurisdiction text not null,
  court_code text not null,
  court_tier bigint not null check (court_tier > 0),
  target_forum text not null default 'Singapore',
  precedential_status text not null check (precedential_status in ('binding', 'persuasive', 'secondary', 'unknown')),
  currency_status text not null default 'not_verified' check (currency_status in ('current_reviewed', 'negative_treatment', 'not_verified')),
  reviewed_by uuid references auth.users(id) on delete restrict,
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (organisation_id, authority_id, target_forum)
);

create table public.authority_relationships (
  id bigint generated always as identity primary key,
  organisation_id bigint not null references public.organisations(id) on delete restrict,
  source_authority_id bigint not null references public.authorities(id) on delete restrict,
  target_authority_id bigint not null references public.authorities(id) on delete restrict,
  treatment text not null check (treatment in ('follows', 'applies', 'distinguishes', 'limits', 'criticises', 'overrules', 'cites')),
  paragraph_labels text[] not null check (cardinality(paragraph_labels) > 0),
  source_document_hash text not null check (length(source_document_hash) = 64),
  review_status text not null default 'draft' check (review_status in ('draft', 'approved', 'rejected', 'superseded')),
  reviewed_by uuid references auth.users(id) on delete restrict,
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (organisation_id, source_authority_id, target_authority_id, treatment, source_document_hash)
);

create table public.practitioner_feedback (
  id bigint generated always as identity primary key,
  public_id uuid not null default gen_random_uuid() unique,
  organisation_id bigint not null references public.organisations(id) on delete restrict,
  audit_claim_id bigint not null references public.audit_claims(id) on delete restrict,
  submitted_by uuid not null references auth.users(id) on delete restrict,
  category text not null check (category in (
    'wrong_verdict', 'wrong_proposition', 'wrong_pinpoint', 'incorrect_case_map_role',
    'missing_authority', 'missing_context', 'outdated_authority', 'other'
  )),
  explanation text not null,
  proposed_citation text,
  proposed_paragraph text,
  proposed_correction text,
  status text not null default 'under_review' check (status in ('submitted', 'under_review', 'accepted', 'rejected')),
  resolution_note text,
  resolved_by uuid references auth.users(id) on delete restrict,
  resolved_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.reference_sources (
  id bigint generated always as identity primary key,
  public_id uuid not null default gen_random_uuid() unique,
  organisation_id bigint not null references public.organisations(id) on delete restrict,
  source_type text not null check (source_type in ('licensed_metadata', 'journal', 'textbook', 'commentary', 'other_secondary')),
  title text not null,
  author text,
  publication text,
  publication_year bigint check (publication_year between 1800 and 2200),
  source_url text check (source_url is null or source_url like 'https://%'),
  verification_status text not null default 'unverified' check (verification_status in ('verified_metadata', 'unverified', 'rejected')),
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now()
);

create index source_imports_org_created_idx on public.source_imports (organisation_id, created_at desc);
create index source_imports_imported_by_idx on public.source_imports (imported_by);
create index source_imports_citation_hash_idx on public.source_imports (normalised_citation_key, document_hash);
create index case_map_runs_org_status_created_idx on public.case_map_runs (organisation_id, status, created_at desc);
create index case_map_runs_authority_id_idx on public.case_map_runs (authority_id) where authority_id is not null;
create index case_map_runs_source_import_id_idx on public.case_map_runs (source_import_id) where source_import_id is not null;
create index case_map_runs_created_by_idx on public.case_map_runs (created_by);
create index case_map_runs_reviewed_by_idx on public.case_map_runs (reviewed_by) where reviewed_by is not null;
create index case_map_runs_hash_idx on public.case_map_runs (document_hash, schema_version);
create index case_map_annotations_run_idx on public.case_map_annotations (case_map_run_id, review_status);
create index case_map_review_events_run_created_idx on public.case_map_review_events (case_map_run_id, created_at);
create index case_map_review_events_annotation_idx on public.case_map_review_events (annotation_id) where annotation_id is not null;
create index case_map_review_events_actor_idx on public.case_map_review_events (actor_id) where actor_id is not null;
create index authority_assessments_org_idx on public.authority_assessments (organisation_id, precedential_status);
create index authority_assessments_authority_idx on public.authority_assessments (authority_id);
create index authority_assessments_reviewer_idx on public.authority_assessments (reviewed_by) where reviewed_by is not null;
create index authority_relationships_org_status_idx on public.authority_relationships (organisation_id, review_status);
create index authority_relationships_source_idx on public.authority_relationships (source_authority_id);
create index authority_relationships_target_idx on public.authority_relationships (target_authority_id);
create index authority_relationships_reviewer_idx on public.authority_relationships (reviewed_by) where reviewed_by is not null;
create index practitioner_feedback_org_status_created_idx on public.practitioner_feedback (organisation_id, status, created_at desc);
create index practitioner_feedback_claim_idx on public.practitioner_feedback (audit_claim_id);
create index practitioner_feedback_submitted_by_idx on public.practitioner_feedback (submitted_by);
create index practitioner_feedback_resolved_by_idx on public.practitioner_feedback (resolved_by) where resolved_by is not null;
create index reference_sources_org_created_idx on public.reference_sources (organisation_id, created_at desc);
create index reference_sources_created_by_idx on public.reference_sources (created_by);

alter table public.source_imports enable row level security;
alter table public.case_map_runs enable row level security;
alter table public.case_map_annotations enable row level security;
alter table public.case_map_review_events enable row level security;
alter table public.authority_assessments enable row level security;
alter table public.authority_relationships enable row level security;
alter table public.practitioner_feedback enable row level security;
alter table public.reference_sources enable row level security;

revoke all on table public.source_imports, public.case_map_runs, public.case_map_annotations,
  public.case_map_review_events, public.authority_assessments, public.authority_relationships,
  public.practitioner_feedback, public.reference_sources from anon, authenticated;

grant select on table public.source_imports, public.case_map_runs, public.case_map_annotations,
  public.case_map_review_events, public.authority_assessments, public.authority_relationships,
  public.practitioner_feedback, public.reference_sources to authenticated;

grant select, insert, update, delete on table public.source_imports, public.case_map_runs,
  public.case_map_annotations, public.case_map_review_events, public.authority_assessments,
  public.authority_relationships, public.practitioner_feedback, public.reference_sources to service_role;
grant usage, select on all sequences in schema public to service_role;

create policy source_imports_member_read on public.source_imports for select to authenticated using (
  exists (select 1 from public.organisation_members m where m.organisation_id = source_imports.organisation_id and m.user_id = (select auth.uid()))
);
create policy case_map_runs_member_read on public.case_map_runs for select to authenticated using (
  exists (select 1 from public.organisation_members m where m.organisation_id = case_map_runs.organisation_id and m.user_id = (select auth.uid()))
);
create policy case_map_annotations_member_read on public.case_map_annotations for select to authenticated using (
  exists (select 1 from public.case_map_runs cm join public.organisation_members m on m.organisation_id = cm.organisation_id where cm.id = case_map_annotations.case_map_run_id and m.user_id = (select auth.uid()))
);
create policy case_map_review_events_member_read on public.case_map_review_events for select to authenticated using (
  exists (select 1 from public.case_map_runs cm join public.organisation_members m on m.organisation_id = cm.organisation_id where cm.id = case_map_review_events.case_map_run_id and m.user_id = (select auth.uid()))
);
create policy authority_assessments_member_read on public.authority_assessments for select to authenticated using (
  exists (select 1 from public.organisation_members m where m.organisation_id = authority_assessments.organisation_id and m.user_id = (select auth.uid()))
);
create policy authority_relationships_member_read on public.authority_relationships for select to authenticated using (
  exists (select 1 from public.organisation_members m where m.organisation_id = authority_relationships.organisation_id and m.user_id = (select auth.uid()))
);
create policy practitioner_feedback_member_read on public.practitioner_feedback for select to authenticated using (
  exists (select 1 from public.organisation_members m where m.organisation_id = practitioner_feedback.organisation_id and m.user_id = (select auth.uid()))
);
create policy reference_sources_member_read on public.reference_sources for select to authenticated using (
  exists (select 1 from public.organisation_members m where m.organisation_id = reference_sources.organisation_id and m.user_id = (select auth.uid()))
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
