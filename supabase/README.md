# Supabase setup

Target project: `zxjaccusnmunjgktzkme`.

The migration files under `supabase/migrations/` are the deployment source of
truth. `seed.sql` contains only public case-law pilot data; it does not create
Auth users or organisations. The `schemas/` files are reference material for
review and are not a substitute for migration history.

## Current project state

The hosted project has been reconciled without deleting its existing demo
organisation, membership, authorities, or passages. The initial schema was
verified against a read-only remote dump and recorded as migration
`20260905073113`; migrations through
`20260906020000_tier0_integrity_provenance.sql` are applied.

Verify status with:

```powershell
$cachePath = Join-Path $env:TEMP "proofmark-npm-cache"
npx.cmd --yes --cache $cachePath supabase@latest migration list
```

For future changes, create a timestamped migration, test it locally, review
the SQL, and deploy only with:

```powershell
npx.cmd --yes --cache $cachePath supabase@latest db push
```

Do not run `migration repair` unless the live schema has been independently
dumped and the exact migration already exists there. Never use `db reset` on
this project.

The generated `remote_public_schema.sql` is a schema-only reconciliation
artifact; it contains no row data and is not read by the application.

Run the database tests after Docker is available:

```powershell
npx.cmd --yes --cache $cachePath supabase@latest test db
```

Do not place the database password, access token, or service-role/secret key in
this directory. The FastAPI service is the only component allowed to hold the
server-side secret.

## Connect the first demo account

After creating the user in Supabase Auth, run the following in SQL Editor with
the real Auth UUID:

```sql
insert into public.organisations (name, slug)
values ('ProofMark Demo', 'proofmark-demo')
returning id;

insert into public.organisation_members (organisation_id, user_id, role)
values (<returned organisation id>, '<auth user uuid>', 'owner');
```

The browser receives SELECT-only grants. The API validates the user's JWT and
membership, then uses the server-side secret to write audit runs, derived
claims, evidence relations, handoffs, and events.
