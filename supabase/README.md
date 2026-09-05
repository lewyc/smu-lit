# Supabase setup

Target project: `zxjaccusnmunjgktzkme`.

The source of truth is split into `schemas/01_tables.sql` and
`schemas/02_security.sql`; `seed.sql` contains only public case-law pilot
data. It does not create Auth users or organisations.

## Apply

Install the Supabase CLI, link the project, create a migration with
`supabase migration new proofmark_initial`, then place the reviewed schema SQL
in that generated migration. Apply with `supabase db push`, seed, and run:

```powershell
supabase test db
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
