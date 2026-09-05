begin;
select plan(14);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data, created_at, updated_at
) values
  ('11111111-1111-1111-1111-111111111111', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'a@example.test', '', now(), '{}', '{}', now(), now()),
  ('22222222-2222-2222-2222-222222222222', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'b@example.test', '', now(), '{}', '{}', now(), now())
on conflict (id) do nothing;

insert into public.organisations (name, slug)
values ('RLS A', 'rls-a'), ('RLS B', 'rls-b')
on conflict (slug) do nothing;

insert into public.organisation_members (organisation_id, user_id, role)
values
  ((select id from public.organisations where slug = 'rls-a'), '11111111-1111-1111-1111-111111111111', 'owner'),
  ((select id from public.organisations where slug = 'rls-b'), '22222222-2222-2222-2222-222222222222', 'owner')
on conflict (organisation_id, user_id) do nothing;

insert into public.audit_runs (
  organisation_id, created_by, input_text, status, corpus_version, engine_version,
  parser_mode, processing_duration_ms, completed_at
) values
  ((select id from public.organisations where slug = 'rls-a'), '11111111-1111-1111-1111-111111111111', 'RLS fixture A', 'complete', 'test', 'test', 'local', 1, now()),
  ((select id from public.organisations where slug = 'rls-b'), '22222222-2222-2222-2222-222222222222', 'RLS fixture B', 'complete', 'test', 'test', 'local', 1, now());

insert into public.audit_claims (
  audit_run_id, claim_order, claim_text, proposition_code, parser_confidence,
  parser_used, verdict, rationale, escalation_required
)
select id, 1, 'fixture claim', 'activity_scope', 1, 'local', 'context_review', 'fixture', true
from public.audit_runs where input_text in ('RLS fixture A', 'RLS fixture B');

insert into public.source_imports (
  organisation_id, imported_by, filename, expected_citation,
  normalised_citation_key, document_hash
) values
  ((select id from public.organisations where slug = 'rls-a'), '11111111-1111-1111-1111-111111111111', 'a.pdf', '[2025] SGHC 1', '2025SGHC1', repeat('a', 64)),
  ((select id from public.organisations where slug = 'rls-b'), '22222222-2222-2222-2222-222222222222', 'b.pdf', '[2025] SGHC 2', '2025SGHC2', repeat('b', 64));

insert into public.case_map_runs (
  organisation_id, source_import_id, created_by, normalised_citation_key,
  document_hash, schema_version, model_version, prompt_version, annotator_version, status
)
select organisation_id, id, imported_by, normalised_citation_key, document_hash,
  'test-schema', 'test-model', 'test-prompt', 'test-annotator', 'draft'
from public.source_imports;

insert into public.case_map_review_events (case_map_run_id, actor_id, event_type)
select id, created_by, 'edit' from public.case_map_runs
where normalised_citation_key = '2025SGHC1';

insert into public.practitioner_feedback (
  organisation_id, audit_claim_id, submitted_by, category, explanation
)
select run.organisation_id, claim.id, run.created_by, 'wrong_verdict', 'fixture feedback'
from public.audit_claims claim join public.audit_runs run on run.id = claim.audit_run_id;

set local role anon;
select throws_ok(
  'select * from public.audit_runs',
  '42501',
  NULL,
  'anonymous users have no table access'
);

select throws_ok(
  'select * from public.corpus_refresh_runs',
  '42501',
  NULL,
  'anonymous users have no corpus refresh metadata access'
);

reset role;
set local role authenticated;
select set_config('request.jwt.claim.sub', '11111111-1111-1111-1111-111111111111', true);

select results_eq(
  $$ select input_text from public.audit_runs order by input_text $$,
  $$ values ('RLS fixture A'::text) $$,
  'a member reads only their organisation audit'
);

select results_eq(
  $$ select count(*)::bigint from public.audit_runs where input_text = 'RLS fixture B' $$,
  $$ values (0::bigint) $$,
  'cross-organisation audit is denied by RLS'
);

select throws_ok(
  $$ insert into public.audit_claims (
       audit_run_id, claim_order, claim_text, proposition_code, parser_confidence,
       parser_used, verdict, rationale, escalation_required
     ) values (
       (select id from public.audit_runs limit 1), 1, 'tamper', 'activity_scope',
       1, 'local', 'verified', 'tamper', false
     ) $$,
  '42501',
  NULL,
  'authenticated clients cannot insert derived claims'
);

select throws_ok(
  $$ update public.audit_runs set engine_version = 'tampered' $$,
  '42501',
  NULL,
  'authenticated clients cannot update audit runs'
);

select results_eq(
  $$ select count(*)::bigint from public.authorities $$,
  $$ select count(*)::bigint from public.authorities $$,
  'authenticated users can read the shared authority corpus'
);

select throws_ok(
  $$ insert into public.corpus_refresh_runs (
       profile_version, status, requested_limit
     ) values ('test', 'queued', 1) $$,
  '42501',
  NULL,
  'authenticated browser clients cannot create corpus refreshes'
);

select results_eq(
  $$ select normalised_citation_key from public.case_map_runs order by normalised_citation_key $$,
  $$ values ('2025SGHC1'::text) $$,
  'a member reads only their organisation Case Maps'
);

select results_eq(
  $$ select count(*)::bigint from public.practitioner_feedback $$,
  $$ values (1::bigint) $$,
  'a member reads only their organisation feedback'
);

select throws_ok(
  $$ update public.case_map_runs set status = 'approved' $$,
  '42501',
  NULL,
  'authenticated browser members cannot approve Case Maps'
);

select throws_ok(
  $$ insert into public.practitioner_feedback (
       organisation_id, audit_claim_id, submitted_by, category, explanation
     ) values (
       (select id from public.organisations where slug = 'rls-a'),
       (select id from public.audit_claims limit 1),
       '11111111-1111-1111-1111-111111111111', 'other', 'browser tamper'
     ) $$,
  '42501',
  NULL,
  'feedback mutations are routed through FastAPI'
);

select throws_ok(
  $$ insert into public.legal_currency_records (
       organisation_id, authority_id, record_type, treatment, source_authority_id
     ) values (
       (select id from public.organisations where slug = 'rls-a'),
       1, 'later_treatment', 'limits', 1
     ) $$,
  '42501',
  NULL,
  'authenticated browser members cannot write lawyer-reviewed currency records'
);

reset role;
select throws_ok(
  $$ update public.case_map_review_events set reason = 'rewrite history' $$,
  'P0001',
  'Case Map review events are append-only',
  'review history cannot be overwritten'
);

select * from finish();
rollback;
