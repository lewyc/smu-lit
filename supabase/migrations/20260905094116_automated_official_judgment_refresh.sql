-- ProofMark automated official-judgment refresh.
-- Existing hand-labelled data becomes benchmark-only and no longer an active runtime corpus.

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
  add column profile_version text,
  add column refresh_run_id bigint references public.corpus_refresh_runs(id) on delete restrict,
  add column snapshot_created_at timestamptz;

alter table public.authority_corpora
  drop constraint authority_corpora_source_status_check;
update public.authority_corpora
  set source_status = 'gold_fixture',
      is_active = false;
alter table public.authority_corpora
  add constraint authority_corpora_source_status_check
  check (source_status in ('gold_fixture', 'officially_sourced'));

alter table public.authorities
  add column assessment_status text not null default 'gold_fixture',
  add column source_host text,
  add column discovery_query text,
  add column retrieved_at timestamptz,
  add column document_hash text,
  add column extractor_version text;
alter table public.authorities
  drop constraint authorities_source_status_check;
update public.authorities set source_status = 'gold_fixture';
alter table public.authorities
  add constraint authorities_source_status_check
  check (source_status in ('gold_fixture', 'officially_sourced', 'rejected')),
  add constraint authorities_assessment_status_check
  check (assessment_status in ('gold_fixture', 'ai_supported', 'unannotated', 'rejected')),
  add constraint authorities_document_hash_check
  check (document_hash is null or length(document_hash) = 64);

alter table public.authority_passages
  add column source_provenance text not null default 'gold_fixture',
  add column assessment_status text not null default 'gold_fixture',
  add column annotation_model text,
  add column annotation_version text,
  add column annotation_confidence numeric(4, 3),
  add column outcome_direction text not null default 'unknown',
  add column local_proposition text,
  add column annotation_disagrees boolean not null default false,
  add column source_text_hash text;
alter table public.authority_passages
  add constraint authority_passages_source_provenance_check
  check (source_provenance in ('officially_sourced', 'gold_fixture', 'rejected')),
  add constraint authority_passages_assessment_status_check
  check (assessment_status in ('gold_fixture', 'ai_supported', 'unannotated', 'rejected')),
  add constraint authority_passages_annotation_confidence_check
  check (annotation_confidence is null or annotation_confidence between 0 and 1),
  add constraint authority_passages_outcome_direction_check
  check (outcome_direction in ('supports_enforcement', 'limits_enforcement', 'mixed', 'unknown')),
  add constraint authority_passages_source_text_hash_check
  check (source_text_hash is null or length(source_text_hash) = 64);

create index authority_corpora_refresh_run_id_idx
  on public.authority_corpora (refresh_run_id)
  where refresh_run_id is not null;
create index corpus_refresh_runs_status_idx
  on public.corpus_refresh_runs (created_at desc)
  where status in ('queued', 'running');
create index corpus_refresh_runs_requested_by_idx
  on public.corpus_refresh_runs (requested_by)
  where requested_by is not null;

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
      document_hash, extractor_version
    ) values (
      v_corpus_id, v_authority->>'citation', v_authority->>'citation_key',
      v_authority->>'case_name', v_authority->>'court', (v_authority->>'decision_date')::date,
      v_authority->>'official_url', 'officially_sourced',
      coalesce(v_authority->>'assessment_status', 'unannotated'),
      v_authority->>'source_host', v_authority->>'discovery_query',
      nullif(v_authority->>'retrieved_at', '')::timestamptz,
      v_authority->>'document_hash', v_authority->>'extractor_version'
    ) returning id into v_authority_id;

    for v_passage in select * from jsonb_array_elements(v_authority->'passages')
    loop
      insert into public.authority_passages (
        authority_id, external_id, paragraph_label, passage_text, supported_propositions,
        limitations, source_provenance, assessment_status, annotation_model, annotation_version,
        annotation_confidence, outcome_direction, local_proposition, annotation_disagrees,
        source_text_hash
      ) values (
        v_authority_id, v_passage->>'id', v_passage->>'paragraph_label', v_passage->>'text',
        array(select jsonb_array_elements_text(coalesce(v_passage->'supported_propositions', '[]'::jsonb))),
        array(select jsonb_array_elements_text(coalesce(v_passage->'limitations', '[]'::jsonb))),
        'officially_sourced', coalesce(v_passage->>'assessment_status', 'unannotated'),
        v_passage->>'annotation_model', 'evidence-annotator.1',
        nullif(v_passage->>'annotation_confidence', '')::numeric,
        coalesce(v_passage->>'outcome_direction', 'unknown'),
        null, coalesce((v_passage->>'annotation_disagrees')::boolean, false),
        encode(digest(v_passage->>'text', 'sha256'), 'hex')
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

create or replace view public.corpus_coverage_summary
with (security_invoker = true) as
select
  corpus.id as corpus_id,
  authority.court,
  concat((extract(year from authority.decision_date)::int / 5 * 5)::int, '-',
    (extract(year from authority.decision_date)::int / 5 * 5 + 4)::int) as decision_year_band,
  proposition.proposition,
  passage.outcome_direction,
  count(*)::bigint as passage_count
from public.authority_corpora corpus
join public.authorities authority on authority.corpus_id = corpus.id
join public.authority_passages passage on passage.authority_id = authority.id
cross join lateral unnest(passage.supported_propositions) as proposition(proposition)
group by corpus.id, authority.court, decision_year_band, proposition.proposition, passage.outcome_direction;

create or replace function public.prevent_corpus_content_mutation()
returns trigger
language plpgsql
as $$
begin
  raise exception 'Corpus authorities and passages are immutable; create a new corpus version instead';
end;
$$;

create trigger authorities_immutable
before update or delete on public.authorities
for each row execute function public.prevent_corpus_content_mutation();

create trigger authority_passages_immutable
before update or delete on public.authority_passages
for each row execute function public.prevent_corpus_content_mutation();

alter table public.corpus_refresh_runs enable row level security;
revoke all on table public.corpus_refresh_runs from anon, authenticated;
grant select on table public.corpus_refresh_runs to authenticated;
grant select, insert, update, delete on table public.corpus_refresh_runs to service_role;
grant usage, select on sequence public.corpus_refresh_runs_id_seq to service_role;
revoke all on function public.activate_official_corpus_snapshot(
  text, text, text, text, text, timestamptz, bigint, jsonb
) from public, anon, authenticated;
grant execute on function public.activate_official_corpus_snapshot(
  text, text, text, text, text, timestamptz, bigint, jsonb
) to service_role;
revoke all on table public.corpus_coverage_summary from anon, authenticated;
grant select on table public.corpus_coverage_summary to authenticated;

create policy corpus_refresh_runs_authenticated_read on public.corpus_refresh_runs
  for select to authenticated using (true);
