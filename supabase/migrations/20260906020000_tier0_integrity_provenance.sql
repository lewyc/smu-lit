-- ProofMark Tier 0 citation-integrity provenance.
-- Existing rows remain readable; new metadata is conservative by default.

alter table public.authorities
  add column if not exists source_review_status text not null default 'pending',
  add column if not exists source_reviewer text,
  add column if not exists source_reviewed_at timestamptz;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.authorities'::regclass
      and conname = 'authorities_source_review_status_check'
  ) then
    alter table public.authorities
      add constraint authorities_source_review_status_check
      check (source_review_status in ('pending', 'approved'));
  end if;
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.authorities'::regclass
      and conname = 'authorities_source_review_metadata_check'
  ) then
    alter table public.authorities
      add constraint authorities_source_review_metadata_check
      check (
        source_review_status <> 'approved'
        or (source_reviewer is not null and source_reviewed_at is not null)
      );
  end if;
end;
$$;

alter table public.authority_passages
  add column if not exists source_role text not null default 'unreviewed',
  add column if not exists source_role_reviewed boolean not null default false,
  add column if not exists source_role_reviewer text;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.authority_passages'::regclass
      and conname = 'authority_passages_source_role_check'
  ) then
    alter table public.authority_passages
      add constraint authority_passages_source_role_check
      check (source_role in ('unreviewed', 'judicial_holding', 'party_submission', 'dissent', 'obiter', 'procedural_history'));
  end if;
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.authority_passages'::regclass
      and conname = 'authority_passages_source_role_review_check'
  ) then
    alter table public.authority_passages
      add constraint authority_passages_source_role_review_check
      check (
        not source_role_reviewed
        or (source_role <> 'unreviewed' and source_role_reviewer is not null)
      );
  end if;
end;
$$;

-- Tier 0 accepts human-reviewed evidence in addition to benchmark-gold rows.
alter table public.authorities
  drop constraint if exists authorities_assessment_status_check;
alter table public.authorities
  add constraint authorities_assessment_status_check
  check (assessment_status in ('gold_fixture', 'human_reviewed', 'ai_supported', 'unannotated', 'rejected'));

alter table public.authority_passages
  drop constraint if exists authority_passages_assessment_status_check;
alter table public.authority_passages
  add constraint authority_passages_assessment_status_check
  check (assessment_status in ('gold_fixture', 'human_reviewed', 'ai_supported', 'unannotated', 'rejected'));

alter table public.audit_claims
  add column if not exists pinpoint_status text not null default 'not_supplied',
  add column if not exists quote_status text not null default 'not_present',
  add column if not exists citation_identity_status text not null default 'not_assessed',
  add column if not exists source_role_status text not null default 'unreviewed',
  add column if not exists currency_status text not null default 'not_verified';

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.audit_claims'::regclass
      and conname = 'audit_claims_pinpoint_status_check'
  ) then
    alter table public.audit_claims add constraint audit_claims_pinpoint_status_check
      check (pinpoint_status in ('not_supplied', 'matched', 'missing', 'wrong_proposition'));
  end if;
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.audit_claims'::regclass
      and conname = 'audit_claims_quote_status_check'
  ) then
    alter table public.audit_claims add constraint audit_claims_quote_status_check
      check (quote_status in ('not_present', 'matched', 'mismatch', 'unresolved'));
  end if;
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.audit_claims'::regclass
      and conname = 'audit_claims_citation_identity_status_check'
  ) then
    alter table public.audit_claims add constraint audit_claims_citation_identity_status_check
      check (citation_identity_status in ('not_assessed', 'matched', 'malformed', 'unresolved', 'court_code_mismatch', 'case_name_mismatch'));
  end if;
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.audit_claims'::regclass
      and conname = 'audit_claims_source_role_status_check'
  ) then
    alter table public.audit_claims add constraint audit_claims_source_role_status_check
      check (source_role_status in ('unreviewed', 'judicial_holding', 'party_submission', 'dissent', 'obiter', 'procedural_history'));
  end if;
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.audit_claims'::regclass
      and conname = 'audit_claims_currency_status_check'
  ) then
    alter table public.audit_claims add constraint audit_claims_currency_status_check
      check (currency_status in ('current_reviewed', 'negative_treatment', 'not_verified'));
  end if;
end;
$$;

-- Preserve the reviewed source metadata when a new official snapshot is activated.
create or replace function public.activate_official_corpus_snapshot(
  p_version text,
  p_name text,
  p_scope_statement text,
  p_content_hash text,
  p_profile_version text,
  p_snapshot_created_at timestamptz,
  p_refresh_run_id bigint,
  p_authorities jsonb
)
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
  v_corpus_id bigint;
  v_authority_id bigint;
  v_authority jsonb;
  v_passage jsonb;
begin
  insert into public.authority_corpora (
    version, jurisdiction, name, scope_statement, content_hash, source_status,
    profile_version, refresh_run_id, snapshot_created_at, is_active
  ) values (
    p_version, 'Singapore', p_name, p_scope_statement, p_content_hash, 'officially_sourced',
    p_profile_version, p_refresh_run_id, p_snapshot_created_at, false
  ) returning id into v_corpus_id;

  for v_authority in select * from jsonb_array_elements(p_authorities)
  loop
    insert into public.authorities (
      corpus_id, canonical_citation, normalised_citation_key, case_name, court, decision_date,
      official_url, source_status, assessment_status, source_host, discovery_query, retrieved_at,
      document_hash, extractor_version, source_review_status, source_reviewer, source_reviewed_at
    ) values (
      v_corpus_id, v_authority->>'citation', v_authority->>'citation_key',
      v_authority->>'case_name', v_authority->>'court', (v_authority->>'decision_date')::date,
      v_authority->>'official_url', 'officially_sourced',
      coalesce(v_authority->>'assessment_status', 'unannotated'),
      v_authority->>'source_host', v_authority->>'discovery_query',
      nullif(v_authority->>'retrieved_at', '')::timestamptz,
      v_authority->>'document_hash', v_authority->>'extractor_version',
      coalesce(v_authority->>'source_review_status', 'pending'),
      v_authority->>'source_reviewer',
      nullif(v_authority->>'source_reviewed_at', '')::timestamptz
    ) returning id into v_authority_id;

    for v_passage in select * from jsonb_array_elements(v_authority->'passages')
    loop
      insert into public.authority_passages (
        authority_id, external_id, paragraph_label, passage_text, supported_propositions,
        limitations, source_provenance, assessment_status, annotation_model, annotation_version,
        annotation_confidence, outcome_direction, local_proposition, annotation_disagrees,
        source_text_hash, source_role, source_role_reviewed, source_role_reviewer
      ) values (
        v_authority_id, v_passage->>'id', v_passage->>'paragraph_label', v_passage->>'text',
        array(select jsonb_array_elements_text(coalesce(v_passage->'supported_propositions', '[]'::jsonb))),
        array(select jsonb_array_elements_text(coalesce(v_passage->'limitations', '[]'::jsonb))),
        'officially_sourced', coalesce(v_passage->>'assessment_status', 'unannotated'),
        v_passage->>'annotation_model', 'evidence-annotator.1',
        nullif(v_passage->>'annotation_confidence', '')::numeric,
        coalesce(v_passage->>'outcome_direction', 'unknown'),
        null, coalesce((v_passage->>'annotation_disagrees')::boolean, false),
        encode(digest(v_passage->>'text', 'sha256'), 'hex'),
        coalesce(v_passage->>'source_role', 'unreviewed'),
        coalesce((v_passage->>'source_role_reviewed')::boolean, false),
        v_passage->>'source_role_reviewer'
      );
    end loop;
  end loop;

  update public.authority_corpora
    set is_active = false
    where is_active and id <> v_corpus_id;
  update public.authority_corpora set is_active = true where id = v_corpus_id;
  update public.corpus_refresh_runs
    set status = 'complete',
        accepted_documents = jsonb_array_length(p_authorities),
        accepted_passages = (
          select count(*) from jsonb_array_elements(p_authorities) authority,
          jsonb_array_elements(authority->'passages')
        ),
        completed_at = now(),
        duration_ms = extract(epoch from (now() - started_at)) * 1000
    where id = p_refresh_run_id;
  return v_corpus_id;
end;
$$;

revoke all on function public.activate_official_corpus_snapshot(
  text, text, text, text, text, timestamptz, bigint, jsonb
) from public, anon, authenticated;
grant execute on function public.activate_official_corpus_snapshot(
  text, text, text, text, text, timestamptz, bigint, jsonb
) to service_role;
