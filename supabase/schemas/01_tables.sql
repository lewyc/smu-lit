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
  source_status text not null check (source_status in ('gold_fixture', 'officially_sourced')),
  profile_version text,
  refresh_run_id bigint,
  snapshot_created_at timestamptz,
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
  source_status text not null check (source_status in ('gold_fixture', 'officially_sourced', 'rejected')),
  assessment_status text not null check (assessment_status in ('gold_fixture', 'human_reviewed', 'ai_supported', 'unannotated', 'rejected')),
  source_host text,
  discovery_query text,
  retrieved_at timestamptz,
  document_hash text check (document_hash is null or length(document_hash) = 64),
  extractor_version text,
  source_review_status text not null default 'pending' check (source_review_status in ('pending', 'approved')),
  source_reviewer text,
  source_reviewed_at timestamptz,
  check (source_review_status <> 'approved' or (source_reviewer is not null and source_reviewed_at is not null)),
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
  source_role text not null default 'unreviewed' check (source_role in ('unreviewed', 'judicial_holding', 'party_submission', 'dissent', 'obiter', 'procedural_history')),
  source_role_reviewed boolean not null default false,
  source_role_reviewer text,
  check (not source_role_reviewed or (source_role <> 'unreviewed' and source_role_reviewer is not null)),
  source_provenance text not null check (source_provenance in ('officially_sourced', 'gold_fixture', 'rejected')),
  assessment_status text not null check (assessment_status in ('gold_fixture', 'human_reviewed', 'ai_supported', 'unannotated', 'rejected')),
  annotation_model text,
  annotation_version text,
  annotation_confidence numeric(4, 3) check (annotation_confidence is null or annotation_confidence between 0 and 1),
  outcome_direction text not null default 'unknown' check (
    outcome_direction in ('supports_enforcement', 'limits_enforcement', 'mixed', 'unknown')
  ),
  local_proposition text,
  annotation_disagrees boolean not null default false,
  source_text_hash text check (source_text_hash is null or length(source_text_hash) = 64),
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

create table public.corpus_refresh_runs (
  id bigint generated always as identity primary key,
  public_id uuid not null default gen_random_uuid() unique,
  requested_by uuid references auth.users(id) on delete set null,
  source_connector text not null default 'SGCourtsConnector',
  profile_version text not null,
  status text not null check (status in ('queued', 'running', 'complete', 'failed', 'fallback')),
  requested_limit bigint not null check (requested_limit between 1 and 25),
  accepted_documents bigint not null default 0 check (accepted_documents >= 0),
  rejected_documents bigint not null default 0 check (rejected_documents >= 0),
  accepted_passages bigint not null default 0 check (accepted_passages >= 0),
  fallback_reason text,
  started_at timestamptz,
  completed_at timestamptz,
  duration_ms numeric(12, 3) check (duration_ms is null or duration_ms >= 0),
  created_at timestamptz not null default now(),
  check (status not in ('complete', 'fallback') or completed_at is not null)
);

alter table public.authority_corpora
  add constraint authority_corpora_refresh_run_id_fkey
  foreign key (refresh_run_id) references public.corpus_refresh_runs(id) on delete restrict;

create table public.audit_runs (
  id bigint generated always as identity primary key,
  public_id uuid not null default gen_random_uuid() unique,
  organisation_id bigint not null references public.organisations(id) on delete restrict,
  created_by uuid not null references auth.users(id) on delete restrict,
  input_text text not null check (char_length(input_text) between 1 and 20000),
  audit_mode text not null default 'citation_only' check (audit_mode in ('citation_only', 'full')),
  original_question text check (original_question is null or char_length(original_question) <= 5000),
  facts text check (facts is null or char_length(facts) <= 10000),
  status text not null check (status in ('queued', 'running', 'complete', 'failed')),
  corpus_version text not null,
  engine_version text not null,
  parser_mode text not null check (parser_mode in ('local', 'gemini')),
  parser_version text not null default 'local-claims.1',
  audit_cache_key text,
  cache_status text not null default 'miss' check (cache_status in ('hit', 'miss', 'bypassed')),
  source_checked_at timestamptz,
  currency_registry_version text not null default 'currency-none',
  retention_expires_at timestamptz not null default (now() + interval '30 days'),
  re_audited_from_id bigint references public.audit_runs(id) on delete set null,
  processing_duration_ms numeric(12, 3) check (processing_duration_ms >= 0),
  summary_metrics jsonb not null default '{}'::jsonb,
  summary_counts jsonb not null default '{}'::jsonb,
  module_scores jsonb not null default '{}'::jsonb,
  evaluation_provenance jsonb not null default '{}'::jsonb,
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
  pinpoint_status text not null default 'not_supplied' check (pinpoint_status in ('not_supplied', 'matched', 'missing', 'wrong_proposition')),
  quote_status text not null default 'not_present' check (quote_status in ('not_present', 'matched', 'mismatch', 'unresolved')),
  citation_identity_status text not null default 'not_assessed' check (citation_identity_status in ('not_assessed', 'matched', 'malformed', 'unresolved', 'court_code_mismatch', 'case_name_mismatch')),
  source_role_status text not null default 'unreviewed' check (source_role_status in ('unreviewed', 'judicial_holding', 'party_submission', 'dissent', 'obiter', 'procedural_history')),
  currency_status text not null default 'not_verified' check (currency_status in ('current_reviewed', 'negative_treatment', 'not_verified')),
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

create index organisation_members_user_id_idx on public.organisation_members (user_id);
create index organisation_members_organisation_id_idx on public.organisation_members (organisation_id);
create index authorities_corpus_id_idx on public.authorities (corpus_id);
create index authority_corpora_refresh_run_id_idx on public.authority_corpora (refresh_run_id)
  where refresh_run_id is not null;
create index authority_passages_authority_id_idx on public.authority_passages (authority_id);
create index authority_passages_search_idx on public.authority_passages using gin (search_vector);
create index citation_registry_checks_corpus_id_idx on public.citation_registry_checks (corpus_id);
create index corpus_refresh_runs_status_idx on public.corpus_refresh_runs (created_at desc)
  where status in ('queued', 'running');
create index corpus_refresh_runs_requested_by_idx on public.corpus_refresh_runs (requested_by)
  where requested_by is not null;
create index audit_runs_created_by_idx on public.audit_runs (created_by);
create index audit_runs_org_created_idx on public.audit_runs (organisation_id, created_at desc);
create index audit_runs_active_idx on public.audit_runs (created_at)
  where status in ('queued', 'running');
create index audit_runs_cache_lookup_idx
  on public.audit_runs (organisation_id, audit_cache_key, created_at desc)
  where status = 'complete' and audit_cache_key is not null;
create index audit_runs_retention_expiry_idx on public.audit_runs (retention_expires_at)
  where retention_expires_at is not null;
create index audit_runs_re_audited_from_id_idx on public.audit_runs (re_audited_from_id)
  where re_audited_from_id is not null;
create index audit_claims_run_order_idx on public.audit_claims (audit_run_id, claim_order);
create index claim_evidence_claim_idx on public.claim_evidence (audit_claim_id);
create index claim_evidence_passage_idx on public.claim_evidence (passage_external_id);
create index handoff_briefs_reviewed_by_idx on public.handoff_briefs (reviewed_by)
  where reviewed_by is not null;
create index audit_events_run_created_idx on public.audit_events (audit_run_id, created_at);
create index benchmark_runs_created_by_idx on public.benchmark_runs (created_by);
create index benchmark_runs_org_created_idx on public.benchmark_runs (organisation_id, created_at desc);
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
create index legal_currency_records_org_authority_status_idx
  on public.legal_currency_records (organisation_id, authority_id, review_status);
create index legal_currency_records_source_authority_idx
  on public.legal_currency_records (source_authority_id)
  where source_authority_id is not null;
create index legal_currency_records_reviewed_by_idx
  on public.legal_currency_records (reviewed_by)
  where reviewed_by is not null;
create index practitioner_feedback_org_status_created_idx on public.practitioner_feedback (organisation_id, status, created_at desc);
create index practitioner_feedback_claim_idx on public.practitioner_feedback (audit_claim_id);
create index practitioner_feedback_submitted_by_idx on public.practitioner_feedback (submitted_by);
create index practitioner_feedback_resolved_by_idx on public.practitioner_feedback (resolved_by) where resolved_by is not null;
create index reference_sources_org_created_idx on public.reference_sources (organisation_id, created_at desc);
create index reference_sources_created_by_idx on public.reference_sources (created_by);
