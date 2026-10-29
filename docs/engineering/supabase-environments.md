# Supabase environments and hosted handoff

Updated: 2026-10-28. The user selected and explicitly authorized replacement hosted project
`neoapucrxhtwlaqzyikn` for authentication/database use. The additive schema, private bucket,
restricted runtime logins and direct API/guest database connectivity are now **verified**.
The previous hosted project was deleted; never reuse it or its credentials. The working local
application remains independent and has not silently switched to the new endpoint.
The [authenticated foundation](../architecture/authenticated-foundation.md) is the source of truth
for the implemented local foundation. See [implementation status](implementation-status.md) for
application checks and the exact next step.

## Current environments

| Environment | Target | Verified state |
| --- | --- | --- |
| Local fixture | SQLite or local Supabase, API `http://127.0.0.1:54321` | Existing campaign/Check workflow; development-only fixture identity |
| Local authenticated | Docker Supabase API `http://127.0.0.1:54321`, Postgres 54322, private Storage | Real local sign-in, restricted database roles and private Storage tested; no hosted account needed |
| Hosted, previously selected | Deleted project `iuxnwiobswrdzimzrunp` | User-reported deletion on 2026-10-23; previous connection checks below are historical, not current health evidence |
| Hosted, selected | `neoapucrxhtwlaqzyikn`, API `https://neoapucrxhtwlaqzyikn.supabase.co` | 35 additive migrations, 34 `vouch` tables, private `vouch-media` bucket and four restricted LOGIN roles verified 2026-10-28; no fixture seed/Auth user |

## Authorized hosted bootstrap: 2026-10-28

After explicit user authorization, `supabase db push --linked --include-all --skip-vault --yes`
applied all 35 reviewed additive migrations. The command reported no seed or role file. Follow-up
queries verified the `vouch` schema, 34 application tables, private media bucket, empty
`auth.users`, and the four NOLOGIN/NOBYPASSRLS group roles. The known-password local seed was not
sent, Vault/config was not pushed and no fixture tenant was created.

`npm.cmd run supabase:provision:hosted` now validates the exact linked project, reads the CLI's
exact session-pooler metadata, creates or rotates four generated `vouch_runtime_*` LOGIN roles and
grants each exactly one existing group. It refuses privileged roles, unexpected memberships,
another project or malformed pooler metadata. Generated passwords and fetched server keys are
written only to ignored `.local/hosted-credentials-<ref>.json` and `.env.hosted.*` files. The
browser receives only the hosted URL and publishable key. API cleanup and guest Storage use
distinct server-only keys. A repeat run completed successfully and both API and guest logins made
SSL pooler connections as their expected restricted roles.

The ignored web environment now selects hosted Supabase and enables the already configured Google
option. Google identity still cannot grant a workspace. After the first confirmed OAuth login, an
operator must run `npm.cmd run supabase:onboard:hosted -- --auth-subject <exact-uuid>
--organization-slug <slug> --organization-name <name> --role <role>`. This command binds only an
exact confirmed Auth subject, refuses conflicting/revoked mappings and records an audit event.
It does not create an Auth password or infer authority from email/metadata.

## Replacement target gate: 2026-10-24

The user authorized use of the new target and completed CLI login on this laptop. Initially the
reference was absent from the previous account; a fresh project listing now finds the exact
reference with healthy status. Linking succeeded, and the ignored cached reference was re-read
and matched. A metadata-only SELECT through the Management API returned zero base tables in
`public`/`vouch`, no `vouch` schema and no migration-history table. This is not direct API/worker
Postgres connectivity or application-session verification. No application DDL/seed, Auth account,
Storage upload, deployment or config push was performed. The publishable key alone is not a
management token. The optional connector remains unavailable; CLI access works independently.

The successful commands were `supabase projects list --output json`,
`supabase link --project-ref neoapucrxhtwlaqzyikn --agent yes`, and
`supabase db query --linked --project-ref neoapucrxhtwlaqzyikn --output json` with this read-only SQL:

```sql
select to_regnamespace('vouch')::text as runtime_schema,
       to_regclass('supabase_migrations.schema_migrations')::text as migration_history,
       (select count(*) from information_schema.tables
        where table_schema in ('public', 'vouch') and table_type = 'BASE TABLE') as app_table_count;
```

No database password was supplied to these commands. The database
password supplied in chat should be rotated in the dashboard and entered only into ignored
server configuration, not pasted again or placed in command arguments. No supplied credential
is copied into these documents. Do not initialize the repository again.

The schema and runtime bootstrap are complete. Hosted Auth mapping remains empty until a real
user completes OAuth and an operator explicitly provisions membership. Deployment environment,
same-origin routing, monitoring, backup/restore and canary proof remain separate gates.

The web tier now supports an opt-in server-only same-origin proxy through
`VOUCH_INTERNAL_API_ORIGIN`. The value must be a credential-free HTTPS origin (HTTP is accepted
only for loopback), while `NEXT_PUBLIC_API_BASE_URL` must identify the public same-origin
`https://<app>/api/v1` route. Do not place database or provider credentials in either value. The
proxy capability is implemented; no public host/domain has been selected or deployed.

On 2026-10-23 both ignored web/API Supabase URLs were checked and still point to loopback. The
cached CLI link now names the verified replacement target, but remains ignored local metadata,
not runtime authority. Never use the obsolete project reference; keep local scripts explicitly local.

## Historical connection evidence (2026-10-22 only)

The hosted Auth settings endpoint returned HTTP 200 using the supplied publishable key. This
verifies public connectivity/key acceptance, not a user session, tenant authorization or Storage.
Its reported email provider is enabled and signup is not disabled; these settings were not changed
or approved as launch configuration.

Read-only database inspection found no base tables in `public` or `vouch`, no `vouch` schema and no
`supabase_migrations.schema_migrations` table. No application migration, fixture seed, Auth account
provisioning, Storage upload, deployment or paid provider call was performed on hosted.

## Credentials and local CLI state

- The user completed the Supabase CLI browser login. The CLI manages that credential; no access
  token or one-time verification code belongs in source, documentation or application logs.
- `supabase/.temp/project-ref` now names the verified replacement project and is ignored by the
  repository. Another target/machine still needs explicit selection and account verification.
- The supplied `sb_publishable_...` key is a public client key, not a database password, secret key
  or CLI management token. The actual key is deliberately not copied into this document.
- The historical supplied Postgres URL contains `[YOUR-PASSWORD]`; it is not a usable runtime connection URL.
  CLI linking and the read-only queries below succeeded without requesting that password.
  Hosted API/worker database connectivity and restricted runtime credentials remain unconfigured.
- Do not paste database passwords or secret/service-role keys into chat. Configure required secrets
  through ignored server environment files or the deployment secret manager when that gate is
  reached. Never use a `NEXT_PUBLIC_` variable for a server secret.
- The optional Supabase connector remains unavailable. Current CLI project listing/link/SQL prove
  only the named management access; they do not prove hosted application functionality.

## Historical connection commands — do not rerun against the deleted project

The repository is already initialized. Do not run `supabase init` again. On this PowerShell machine
use `npx.cmd`; RTK may wrap these commands with `rtk proxy`.

```powershell
npx.cmd supabase login --agent no
npx.cmd supabase projects list --output json
npx.cmd supabase link --project-ref iuxnwiobswrdzimzrunp --agent no
npx.cmd supabase db query --linked --project-ref iuxnwiobswrdzimzrunp --output json "select table_schema, table_name from information_schema.tables where table_schema in ('public', 'vouch') and table_type = 'BASE TABLE' order by table_schema, table_name"
npx.cmd supabase db query --linked --project-ref iuxnwiobswrdzimzrunp --output json "select to_regclass('supabase_migrations.schema_migrations')::text as migration_history, to_regnamespace('vouch')::text as runtime_schema"
```

The explicit `--agent no` permits interactive browser login; automatic agent mode rejected the
interactive prompt in this environment. Complete verification in the local terminal when possible.
The commands above were actually executed; neither query changes application schema or rows.

## Keep local development separate

Root `supabase:start`, `supabase:migrate`, `supabase:reset` and `supabase:test` scripts target the
local stack; migrate/reset/test explicitly pass `--local`. Reset remains destructive to local data
and was not run during hosted connection setup.
After linking and making the scope explicit, `npm.cmd run supabase:test` passed all 42 local SQL
assertions. Package JSON/local command checks, changed-document links and the archive hash passed;
application type checks, build and browser tests were not rerun for this setup change.
Continue to use explicit `--local` for database commands and the documented loopback connection
for API/worker development. A successful link does not switch the running application to hosted.
Do not replace `VOUCH_DATABASE_URL` with the placeholder hosted URL or point fixture mode at cloud.

Do not run a hosted database reset, `db push`, fixture seed or config push as a connection test:

- `supabase/seed.sql` provisions synthetic Auth users with the known password `fixture-only`,
  fixture organizations and role grants. It is for local development only.
- The initial migration preserves an unused public prototype. Its direct-client mutation policies
  are removed by a later hardening migration; applying the initial file alone is unsafe.
- Authenticated runtime policies and separate API/worker credentials are now implemented and tested
  locally. They have not been deployed to this hosted project. Fixture headers are not authentication.
- `supabase/config.toml` describes local ports, redirects, signup and seed behavior. Its 100 MB
  Storage limit is not the application's 5 MB upload contract or reviewed hosted configuration.

## Next gate before hosted application changes

The authenticated foundation now runs locally. Use `npm.cmd run supabase:provision` to generate
ignored synthetic credentials, then `npm.cmd run dev:authenticated`. Default `npm.cmd run dev`
explicitly retains fixture identity; fixture Postgres URLs must be loopback. Neither mode deploys.

Anchored retention/deletion and bounded local decoded media now run under the documented local
boundaries. Production operational proof remains open. Select a new hosted project only when
deployment is requested, then prepare a separate hosted
bootstrap/migration review without fixture credentials/data, inspect the target again, and obtain
explicit authority for deployment or consequential hosted changes. Linking alone is not that
authority. The local app still rejects staging/production startup.

Current official setup/security references: [CLI login](https://supabase.com/docs/reference/cli/supabase-login),
[CLI link](https://supabase.com/docs/reference/cli/supabase-link) and
[API keys](https://supabase.com/docs/guides/getting-started/api-keys).
