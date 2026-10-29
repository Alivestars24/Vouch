# Authenticated application foundation

Date: 2026-10-22; hosted runtime update 2026-10-28. Status: implemented locally and bootstrapped
on the explicitly authorized hosted project; verification is recorded per command in the execution
ledger. This contract was recorded before code and extends the campaign/Check fixture workflow.
The [implementation status](../engineering/implementation-status.md) is the evidence ledger.

The user reports deleting the previously linked hosted project on 2026-10-23. Earlier connectivity
checks are historical; no current hosted target or replacement cloud credentials are needed for
this local foundation. [Supabase environments](../engineering/supabase-environments.md) records
the stale-link guard. This does not authorize fixture deployment to any new project.

## Outcome and boundaries

A user signs in with Supabase Auth, selects an organization they actively belong to, uploads an
authorized private draft, and completes the existing asynchronous evidence/revision/human approval
workflow. Provider execution remains explicit fixture mode. Identity, database persistence, media
storage and model invocation are independent settings; genuine Auth/Storage does not imply live
Meta results.

Keep one Next.js application, one FastAPI API and one Python worker with a shared domain model.
Use private `vouch` PostgreSQL tables and a private `vouch-media` Storage bucket. Domain mutations
remain API/worker commands; clients cannot write approvals, evidence, budgets or roles directly.
No new queue vendor, autonomous product agents or vector database is needed for this slice.

## Identity and authorization

- `VOUCH_AUTH_MODE=fixture` is retained for deterministic development/test and rejects deployment
  environments. `VOUCH_AUTH_MODE=supabase` requires PostgreSQL and configured trusted Auth URL/key.
- Fixture PostgreSQL must be loopback; it cannot be pointed at hosted data. Both modes still refuse
  staging/production startup until deployment, retention and media-processing gates are complete.
- The browser uses Supabase password sign-in and session refresh. The API receives the current
  `Authorization: Bearer ...` token, verifies it through `GET /auth/v1/user`, and trusts only the
  returned user ID. Neither email nor user-editable metadata can establish membership or roles.
- Runtime `users.auth_subject` uniquely maps the verified Supabase subject to a provisioned domain
  user. The ordinary API cannot change this mapping. No self-selected role or automatic promotion.
- `GET /api/v1/me/workspaces` requires a verified identity but no organization header and returns
  active memberships only. Other member routes require `X-Organization-Id` and recheck membership.
- Authenticated mode rejects fixture identity/role headers. UI sign-out clears workspace state;
  token failures show sign-in recovery. Authentication errors never disclose raw provider bodies.
- Supabase sign-out and token revocation semantics must be tested locally; membership revocation
  is enforced from current database records on every API request, independent of JWT role claims.

## Database credentials and transaction scope

Use separate `vouch_api`, `vouch_worker`, `vouch_guest` and `vouch_retention` PostgreSQL group roles
without LOGIN, superuser or BYPASSRLS. Local and hosted setup provision distinct LOGIN roles that
inherit exactly one group; secrets are written only to ignored environment files. Hosted pooler
usernames bind each login to the exact project ref and require SSL. Bootstrap/migrations use CLI
management authority, never a browser or application runtime credential.

Hosted identity onboarding is deliberately separate from runtime bootstrap. Google/Auth may
establish an exact confirmed subject, but only the operator command can bind that UUID to a domain
user and active organization membership. It refuses email/subject conflicts and revoked membership
reactivation, and records `membership.provisioned`. No first-login auto-owner behavior exists.

API transactions set verified auth subject, domain user and selected organization as local database
context; subsequent transactions in the same request reapply that context. RLS and column/table
grants protect against omitted tenant predicates. Bootstrap identity reads allow only the current
subject and its memberships. Security-definer membership helpers stay in a private schema with a
fixed search path, explicit subject checks and limited EXECUTE grants.

Worker transactions may discover/claim jobs across tenants, then derive tenant scope from the
stored job before reading or publishing related records. Worker cannot grant membership, change
rulebooks or approve content. API cannot use worker privileges to publish evidence. Context is
transaction-local so pooled connections cannot inherit another user's scope.

## Private media contract

- Add `storage_backend` and `object_key` to media metadata. Database byte storage remains the
  deterministic fallback; authenticated mode uses Supabase Storage and retains no duplicate bytes
  in the relational row.
- Expired sources cannot be attached, checked, approved or delivered; worker input/publication
  rechecks the anchored deadline and cancels rather than publishing late evidence. Version-history
  captions are suppressed after source expiry. This deny path is not an automatic physical purge.
- Object keys are server-generated `organization/campaign/asset/source` paths; no arbitrary URL or
  caller-selected bucket/key is accepted. Bucket size/MIME limits match the 5 MB API cap.
- Upload intent and five-minute upload/finalize capabilities remain. Authenticated content PUT
  additionally requires the member bearer token. Storage insert/read policies check current
  organization membership, campaign ownership and asset intent; objects are never public.
- The API uses the caller's token for Storage upload/download. Finalization reads actual stored
  bytes and validates length, MIME signature and hash. Upload retry for an existing deterministic
  key must reconcile identical bytes rather than silently overwrite different content.
- Authenticated media reads recheck tenant scope, source state and tombstones. No permanent public
  URL, token, credential or raw media payload enters logs.
- Deletion commits the tombstone, fences jobs and erases local text before remote deletion. The
  server's cleanup credential is used only for exact domain-resolved object keys. Authenticated
  clients have no direct Storage DELETE grant that could bypass deletion receipts.
- Storage failure produces a partial receipt and a safe retry path; a repeated deletion retries
  pending destinations. Mark complete only after the declared Storage copies are confirmed absent.
  Storage and database changes are not one transaction; durable intent and idempotent retries close
  that gap. [Anchored retention scanning](retention-worker.md) now has a separate scrub-only
  credential, durable claims/fences and bounded retries; its verification is in the ledger.

Attachment, revision and deletion commands additionally take a transaction-local, per-organization
lineage advisory lock before enumerating dependencies. Revisions lock the existing submission;
asset attachment locks and revalidates its source. This prevents a caption-bearing version from
appearing after deletion collected its derivatives. Workers retain submission-first publication
locks and never acquire the lineage gate, which is separate from budget locks. The deliberate
throughput ceiling is serialization of attachment/deletion per tenant; refine only when measured.

Postgres applies UPDATE RLS to `SELECT FOR UPDATE`. Reviewer/viewer source reads therefore have
scoped lock permission with an independent trigger rejecting actual content-pointer/deletion
changes. This preserves the approval/deletion serialization boundary without granting edits.

## Local setup and verification contract

Provide one local-only provisioning command: inspect local Supabase status without printing keys,
apply additive migrations, seed synthetic domain data, provision synthetic `@vouch.test` Auth users,
link subjects, and create separate API/worker login credentials. Refuse non-loopback targets.
Write generated configuration and login details to ignored files; preserve existing user data and
unrelated configuration. No hosted project, paid API call, email delivery or deployment is required.

Implemented command: `npm.cmd run supabase:provision`. It reuses generated credentials across runs
and writes `.local/credentials.json`, backend `.env.api`/`.env.worker`, and web `.env.local`, all
ignored. `npm.cmd run dev:authenticated` uses those separate credentials. `npm.cmd run dev` remains
explicit fixture mode, overriding the web's generated auth setting. Supabase JS owns browser
session storage/refresh; no cookie-authenticated domain mutation or private server-rendered cache
is introduced. API/worker secrets are never public environment variables.

Required proof before claiming this slice verified:

1. Existing SQLite/Postgres fixture suite still passes.
2. Invalid/expired bearer tokens and fixture-header spoofing fail; current membership/role changes
   affect the next request; subject mapping cannot be changed through ordinary API permissions.
3. Real local Supabase password sign-in works through the browser and API. Desktop/mobile complete
   the existing draft, partial evidence, revision and exact-version approval workflow.
4. API/worker role tests exercise real restricted credentials, row scope, pooled connection reset,
   cross-tenant references and forbidden approval/evidence/role mutations.
5. Private Storage rejects anonymous/cross-tenant writes/reads, stores finalized bytes outside
   database rows, and handles interrupted upload/deletion plus retry without false completion.
6. Lint/types/build/OpenAPI and local database advisors pass. Document all unrun or failed gates.

The startup product roadmap retains Find, Check, Try and Track. This foundation precedes guest
invitations, complete media decoding/retention workers, live Meta activation, pilot evaluation and
deployment. Pilot launch still requires verified provider terms, reviewed rulebooks, restoration,
operational ownership and explicit user authority for external publication/spend.
