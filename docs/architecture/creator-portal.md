# Scoped creator invitation portal

Date: 2026-10-23; accepted 2026-10-24. Status: **accepted implementation contract; the local
grant/exchange/session/submission-view foundation plus guest upload/content/finalize, guest-attributed
authorization receipt and one initial immutable version are implemented and verified as of
2026-10-28. Member recovery/renewal preserves the credential family action scope and consumed
quota maxima. Exact-byte content replay and the Supabase guest-upload/deletion fence are also
implemented. Explicit member-selected feedback publication, creator allowlisted reads, historical
labeling and source-erasure scrubbing are implemented. A later revision and withdrawal remain
unimplemented**.
This bounded continuation follows the member workflow, [authenticated foundation](authenticated-foundation.md),
[processing authorization](processing-authorization.md), [media validation](media-validation.md)
and [retention worker](retention-worker.md). Guest descriptions in
[API contracts](api-contracts.md#5-creator-guest-contract) now have a working initial-draft and
feedback slice; the later revision/withdrawal contracts remain design only. Local security evidence is recorded in
[implementation status](../engineering/implementation-status.md). No hosted changes are authorized
by this document; the former hosted project is obsolete.

## Outcome and limits

An authorized member creates an invitation for one campaign, its rostered creator and one logical
submission. The implemented creator path exchanges the link, acknowledges an applicable notice,
uploads a draft, sees its receipt and publishes one initial immutable version. Brand members
initiate Check and reviewers decide approval. An authorized member can explicitly share a bounded
timestamped feedback snapshot; a later immutable creator revision is the next contract, not current
behavior. The portal displays
truthful states such as awaiting brand review, changes requested and approved version N, never
automatic approval.

The grant is a capability, not a workspace membership or proof of the creator's legal identity.
It cannot enumerate organizations, people, campaigns, unrelated assets, internal findings,
reviewer discussions, usage, budgets or audit records. It cannot start Check or other paid work,
change finding decisions, approve, publish externally, extend retention or renew itself.
Provider results remain explicitly fixtures; optional decoded media is a separate setting.

## Accepted grant and exchange lifecycle

- Admin/marketer issuance may create an empty submission assigned to an existing campaign-roster
  creator, or target an existing matching submission. Reviewer issuance is limited to an existing
  matching submission; it does not confer the member's general submission-creation permission.
- Each grant binds tenant, campaign, creator, submission, issuing member, explicit action allowlist,
  expiry and upload quota. Validate the entire stored relationship, including campaign roster,
  rather than trusting a caller's independently valid IDs.
- Generate a random secret with at least 256 bits of entropy. Store only its SHA-256 digest and
  show its invitation URL once. Put the secret in a URL fragment, never query/path parameters.
  The exchange page removes the fragment with history replacement before any subsequent navigation.
  Use `Referrer-Policy: no-referrer`, `Cache-Control: no-store` and no analytics or session recording.
- `POST /api/v1/guest/exchange` consumes an unexpired, unrevoked invitation exactly once under a
  database lock and creates a new independently random session secret. Store only its digest.
  Concurrent exchanges produce at most one session. Unknown, expired, consumed and revoked secrets
  return a uniform safe denial, not campaign metadata.
- Accepted bounds are 48 hours for an invitation, 30 minutes for a session and five minutes for
  upload/finalize capabilities. Session expiry cannot exceed grant expiry; upload authority cannot
  exceed either. Grant/session and upload bounds are implemented and verified.
- Transport is an HttpOnly, SameSite=Strict cookie scoped to `/api/v1/guest`, never a
  Supabase user JWT or a token stored in localStorage. Require Secure outside explicitly local HTTP
  development; deployment remains disabled. Credentialed CORS must remain an exact origin allowlist,
  and unsafe guest commands validate Origin. Exchange/cookie resume has browser proof; the initial
  guest mutation UI has focused component proof, while its full member-to-guest browser journey and
  the later mutation lifecycle remain release work.
- Every request rechecks current session/grant state, expiry, action scope, issuing member's current
  authority, assigned submission and source denial. Renewal requires a member command, creates a
  new grant/secret and revokes old sessions atomically. Never silently extend an old credential.
  Atomically limit each grant to five source reservations and 25,000,000 reserved bytes. Reserve
  both before issuing upload authority; expiry alone does not release an accepted source or count
  unconfirmed cleanup as free capacity. Bound exchange to 10 attempts per 15-minute privacy-minimized
  client bucket and five attempts per 15-minute presented-token-digest bucket. Retain those attempt
  records no longer than 24 hours and return the same safe denial when limited. The implemented
  route stops inserting once either bucket is blocked and has real two-connection concurrency proof;
  hosted exposure still needs a trusted-proxy/client-address contract.

No automatic email or external message delivery is included. A member manually copies the secret
link. Issuance requires a client-held non-secret `recovery_id`; retrying the same immutable scope or
calling explicit member renewal rotates the whole credential family. Plaintext invitation/session
secrets are never retained for replay.

## True guest attribution: additive migration strategy

Do not create a synthetic User, reuse the issuer's Principal or assign a creator the marketer role.
Keep member `Principal` and new `GuestPrincipal` distinct. The latter contains verified tenant,
grant/session/submission IDs and allowed actions, not member roles or a member access token.

Add private runtime tables with RLS and tenant-composite foreign keys:

| Entity | Minimum stored contract |
| --- | --- |
| `guest_grants` | Assigned campaign/creator/submission, issuer member, non-secret recovery ID and renewal root, secret digest, actions, expiry, consumed/revoked times, quota counters; immutable scope after issuance |
| `guest_sessions` | Grant, unique secret digest, original expiry and revocation; stable opaque row ID retained for attribution after the credential expires |
| `creator_feedback` | Submission/version/check/draft references, explicitly selected shared snapshot, publishing member and time; no automatically exposed internal discussions |
| `guest_commands` | Session/operation/idempotency key, normalized request digest and result reference; unique scope for mutation retries, no credential response payloads |

Use composite constraints that prove grant submission, campaign and creator agree, and that the
creator is on that campaign's roster. A composite `(organization_id, id)` FK alone does not prove
all three relationships. Scope guest-owned media to that same submission, including when a member
later attaches it; a member cannot rebind a guest upload to another submission or creator.

Expand existing actor columns without changing historical attribution:

- `media_assets` and `submission_versions`: retain member `uploader_user_id`, make it nullable and
  add `uploader_guest_session_id`; an XOR constraint requires exactly one. The session's stored
  grant establishes the assigned submission. New guest uploads/versions use only the guest branch.
- `consent_receipts`: retain nullable member `actor_user_id`, add `actor_guest_session_id` and an
  XOR constraint. Match its actor exactly to the source uploader. Keep notice/hash/time/purpose
  immutable. Add `revoked_by_guest_session_id` and a guest revocation branch without weakening the
  existing member/actorless-retention checks or allowing revocation reversal.
- `review_events`: allow a guest actor reference only for a revision's `superseded` event.
  Guest role cannot insert approval/rejection/revocation/finding decisions. `approvals` and
  human finding decisions retain mandatory verified member attribution and reviewer authority.
- `audit_events` and `deletion_requests`: add guest session attribution where applicable and a
  truthful `guest` kind, with no invented member ID. Preserve existing actorless worker/retention
  semantics. Do not place secrets, captions, media or complete feedback in safe metadata.

Backfill only the structural member branch for rows already carrying a member ID; do not create
receipts for legacy assets or reinterpret an old member acknowledgment as creator consent.
PostgreSQL actor/source guards and worker receipt reads must understand both genuine actor branches.
SQLite upgrades need the same constraints; use a transactional, tested table-copy migration where
SQLite cannot relax an existing NOT NULL constraint. Preserve existing data and archived sources.
Do not edit previous migrations or reset the database to make actor expansion convenient.

## Applicable immutable notice and withdrawal

The current notice explicitly says the acknowledgment is made as a workspace member. A guest must
not accept that text. Publish a new immutable, applicable notice version/hash; retain the existing
registry entry and historical hashes unchanged. Explain link-possession attribution, fixture-only
providers, optional decoding, anchored retention, cleanup limits and how a creator requests help.
Collect separate affirmative notice acknowledgment and rights attestation for every fresh source.
This still is not proof of consent from every depicted person or legal review of the notice.

An expired/revoked grant removes portal access. It does not revoke an already valid processing
receipt, erase a source or extend its original retention deadline. Analysis authorization checks
receipt provenance/revocation and source state, not whether the old upload session remains active.

An explicit guest withdrawal action may target only that guest grant's own source receipt within
its assigned submission. It uses the existing irreversible revocation plus durable erasure workflow,
not an independent delete endpoint. A member's existing role-scoped withdrawal remains available.
An expired-link recovery/contact path must not promise a universal self-service privacy-rights
process or issue a broader replacement session.

## Shared media primitives, separate authorization

Current upload/finalize services require member ownership and re-read membership/roles after media
decoding. Extract only actor-neutral source validation, processing snapshot and publication helpers.
Keep separate member and guest permission resolvers, each rechecked before staging and after the
decoder/remote I/O. Never call a member service with a forged Principal merely to reuse code.

Implemented initial-draft guest routes accept no tenant, campaign, creator or arbitrary object-key authority from payloads:

- `GET /guest/submission`: allowlisted assigned-submission/receipt/status/feedback DTO only.
- `POST /guest/uploads`, `PUT /guest/uploads/{id}/content`,
  `POST /guest/uploads/{id}/finalize`: same bounded bytes, five-minute capability, exact ownership,
  active notice and measured-media checks as member intake, plus current guest-session authority.
  Retrying a validated content `PUT` succeeds only when the server-measured hash and length are
  identical; it does not upload again or regress source state. Changed bytes conflict, and the
  session/grant/capability window is still enforced on the replay.
- `POST /guest/submission-versions`: initial version of the one empty assigned logical submission;
  idempotency prevents duplicate publication. A non-empty/current submission is rejected until the
  later revision contract is implemented.
- `POST /checks/{analysis_id}/creator-feedback`: member-only explicit publication of selected text
  and an optional measured timestamp range. The immutable record binds the current version, exact
  analysis/manifest/invocation/status, selected draft, publisher and actor-scoped idempotency key.
  `GET /guest/submission` returns only that allowlisted snapshot and marks earlier-version feedback
  historical.

Scoped receipt withdrawal is implemented for the exact grant-owned source with no generic by-ID
traversal. Broader source-media reads remain unavailable.

The later revision route must supersede the prior current review context and record the actual guest
actor. It cannot inherit an approval. Approval display must identify the exact currently approved
immutable version, not copy a prior green state onto a revision.

## Database and Storage authority

The implementation adds a separate non-superuser, non-BYPASSRLS `vouch_guest` group and local login credential/pool.
The ordinary member pool must not acquire guest authority through an untrusted request header.
Extend the allowlisted runtime role/context support with guest session/grant scope set only after
opaque-token verification and reapplied transaction-locally. Pool reuse cannot retain old scope.
Exchange lookup/consumption needs a narrowly reviewed private helper or hash-scoped policy; it
must not grant anonymous table enumeration. Any security-definer helper needs fixed search path,
explicit predicates and restricted EXECUTE, never default PUBLIC access.

Guest RLS permits only its assigned rows and explicitly owned staged sources. It cannot write
membership, rules, analysis/evidence, budgets, jobs or approvals. Member/worker/retention grants must
be updated only for the new lineage/attribution, not replaced with a broad common role.

There is no caller Supabase user JWT for guest Storage. Preserve the existing caller-JWT path for
members. Guest media transport is an API-proxied, exact-object-key adapter using a separate
explicit server-only Storage credential; it must never fall back to a member token or expose a key
to the browser. This credential may bypass Storage RLS: it is not a narrowly scoped guest identity.
ADR-029 accepts that tradeoff subject to adversarial tests; the existing cleanup-only credential
contract must not silently widen to guest reads/writes.
Validate current guest scope and source state on every operation, enforce immutable key/bytes and
persist remote artifact intent before I/O. Do not introduce irrevocable public URLs or claim
provider-signed upload/revocation behavior that has not been verified.

For the implemented Supabase guest content write, retain the tenant-lineage and exact-source
database locks while the bounded private Storage operation runs. This serializes member deletion
against a possible late object: deletion cannot mark the source complete and then have that write
appear afterward. If Storage returns an ambiguous failure, roll back the database transaction;
the next request uses the same exact object key to reconcile what exists remotely before deciding
whether to write. A validated same-hash/same-length replay is acknowledgment, not another upload;
different bytes are a conflict.

## Lineage, revocation and cleanup races

Keep tenant lineage gate → ordered submission lock → ordered source lock → review-context/job
order for attachment, revision, final publication and deletion. Guest mutation phases acquire the
tenant lineage gate first, then their grant/session/command locks, then the existing submission/
source order. Exchange may perform a read-only secret-digest lookup to discover tenant scope,
but must acquire that lineage gate before locking/rechecking/consuming the grant. Member grant
revocation follows the same lineage-first rule; do not hold a grant lock while waiting for lineage.
Re-read mutable permission/source state after external work. Revoke versus publish must be atomic:
a prior successful token lookup is insufficient authority to publish later. The implemented guest
Storage path is the bounded exception to the usual short-transaction I/O shape: it keeps the
lineage and exact-source locks through the private write so deletion cannot outrun a late object,
then commits the measured state or rolls the transaction back for exact-key reconciliation.

Submission/source deletion denies relevant guest access before serving new media or feedback.
Extend erasure traversal to guest staged sources and published feedback snapshots; scrub content
while retaining only declared minimal grant/session/receipt/audit identifiers. Expiring, unbound
uploads still have anchored retention and exact remote keys for cleanup. A guest session ending
does not erase or reset these cleanup obligations.

Reuse prepared-container accounting, tombstones, existing actorless retention authority, retry
budget, receipt leases/fences and per-destination completion checks. Do not give the guest direct
Storage DELETE or a way to mark a deletion receipt completed. A revoked/expired guest may lose
portal access while server cleanup retries safely continue. Register late remote artifacts only
for cleanup, never for delivery after revocation/deletion.

## Explicit feedback publication

`FixRequestDraft` remains `draft_only`. A separate authorized member action now publishes
an allowlisted snapshot for the assigned creator and an exact submission version/check manifest.
Only chosen timestamps, requested changes and member-approved explanatory text are shared.
Never return `check_dict`, raw findings, reviewer rationale, roster or billing DTOs wholesale.
Keep original fixture/coverage provenance truthful where shared; absence of shared feedback is not
an all-clear. Feedback for an earlier version is marked historical, not presented as new
instructions for a later version. Source deletion scrubs its message and optional range through the
same lineage cleanup. Guest withdrawal uses the exact receipt, active assignment and renewal-family
lineage, then returns the existing durable deletion receipt.

## Implementation surface and proof required

Expected files: new `guest_auth.py`, `guest_service.py` and guest route/DTO modules; focused actor
and shared-source changes in `models.py`, `service.py`, `schemas.py`, `auth.py`, `api.py`, `db.py`,
`notices.py`, `storage.py`, `config.py`, local provisioning and retention traversal. Add an additive
CLI-created migration, SQL policies/guards, fixture upgrades and generated OpenAPI/TypeScript wire
types. The portal should have a separate Next.js entry and exact DTO normalizers, not mount the
member workspace shell. Update the index, requirements, contracts, experience, decisions and status
as implementation proceeds.

The implemented invitation, initial mutation and feedback subset has passing coverage for recovery/renewal, simultaneous exchange,
tampering/replay, expiry/revocation, issuer authority, restricted database credentials, allowlisted
DTOs and desktop/mobile fragment/cookie behavior. The list below remains the completion gate for
the full mutation journey:

1. Real guest actor XOR/FK attribution, immutable member/guest receipts, no legacy backfill and
   SQLite/Postgres upgrade preserving existing sources/history.
2. Simultaneous exchange, tampering, reuse, expiry, quota/idempotency and grant/session revocation;
   issuer role/membership loss; no credential leakage to URL logs, referrers or browser traces.
3. Two tenants and two creators in one tenant: guessed IDs, altered keys, same-campaign rebind,
   member-route access, roster enumeration, Check/budget/approval attempts all denied.
4. Restricted guest database credentials and pooled context reset; Storage proxy denial paths,
   interrupted/retried upload and identical-byte reconciliation without broader Storage access.
5. Missing/stale/false notice, true actor receipt, explicit withdrawal, legacy source denial and
   old notice/hash preservation; grant expiry does not fabricate consent revocation.
6. Decoder and remote I/O racing grant revoke, source withdrawal, revision and retention; no late
   publication, approval inheritance, orphan artifact or false cleanup completion.
7. Explicit-only feedback publication, internal-data exclusion, exact-source withdrawal and deletion scrubbing are covered
   in service, SQL, restricted-runtime and component tests. Desktop/mobile initial draft plus
   feedback, revision, exact-version brand approval and expired-link recovery remain a full browser
   release journey. Report only commands actually run and leave hosted/live-provider gates separate.

## Discovery evidence

Read-only source discovery on 2026-10-23 found the key seams in member `Principal`, member-specific
`upload_intent`/`_finalization_source`, receipt-active checks, lineage locking, `audit`, revision
supersession, `FixRequestDraft` and shared source erasure. The existing Codebase Memory graph was
consulted with search, trace and snippets, then coverage checks. Its generation is 2026-10-22;
changed/untracked files required direct-source fallback. No new index, application edits, server
execution, provider calls or hosted operations were performed for that design pass.
