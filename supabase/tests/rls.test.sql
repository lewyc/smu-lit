begin;
select plan(6);

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

set local role anon;
select throws_ok(
  'select * from public.audit_runs',
  '42501',
  'anonymous users have no table access'
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
  'authenticated clients cannot insert derived claims'
);

select throws_ok(
  $$ update public.audit_runs set engine_version = 'tampered' $$,
  '42501',
  'authenticated clients cannot update audit runs'
);

select results_eq(
  $$ select count(*)::bigint from public.authorities $$,
  $$ select count(*)::bigint from public.authorities $$,
  'authenticated users can read the shared authority corpus'
);

select * from finish();
rollback;
