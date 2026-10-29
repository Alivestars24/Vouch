# Application and provider contracts

Status: implemented local fixture/Supabase-authenticated HTTP contract with generated OpenAPI at
`services/backend/openapi.json`. The current web client consumes typed application DTOs and the
workflow is contract-tested through FastAPI. The implemented contract step generates TypeScript
from local OpenAPI, checks generated-file freshness, and types outgoing command bodies. The
current fail-closed response normalization stays in place: generation is not runtime validation.
See [implementation status](../engineering/implementation-status.md).

### Implemented type-generation boundary (2026-10-23)

Use pinned `openapi-typescript` as a development-only generator over the committed local FastAPI
schema; no network schema fetch, runtime client framework or extra production dependency. Generate
`apps/web/src/lib/generated/api.ts` after `openapi` and compare it in `contracts:check`, which
also compares the Python schema without mutating either artifact. `check` runs freshness first.
Import generated request component types for campaign/upload/finalize/submission/Check/finding/
review/fix/deletion commands, including strict notice acknowledgment fields. Keep camelCase view
models separate from wire types. Add explicit response schemas for immutable notices and scoped
receipt reads first; other dictionary response envelopes remain generic until incrementally typed.
Do not cast arbitrary incoming JSON into trusted authorization or replace fail-closed provenance
checks with a TypeScript assertion. No API keys, credentials or authenticated schema fetch needed.
`UploadIntentCreate.notice_acknowledged` is `const:true` in OpenAPI and generated types, with the
existing strict runtime validator still rejecting false/coerced input. MIME/scenario values are
narrowed before an outgoing request; invalid choices do not create a capability or job.

### Current execution contract

The accepted [OAuth/storage extension](oauth-storage-motion.md) adds `GET /storage/usage` for a
current scoped member, including viewers. `StorageUsageResponse` contains integer byte fields
`limit_bytes`, `used_bytes`, `reserved_bytes`, `pending_cleanup_bytes`, `available_bytes`,
`max_upload_bytes`, plus `storage_backend:database|supabase`. Categories are disjoint;
available is `max(0, limit - used - reserved - pending_cleanup)`. Malformed or inconsistent
responses fail closed in the web client. This is workspace accounting, not provider billing.
New upload intents reserve the entire per-file maximum atomically (direct Storage uploads cannot
be trusted to use only their declared size); insufficient capacity returns a safe quota error.
The Google callback is a web route, not an API endpoint or membership-provisioning capability.

`GET /notices/campaign-check` and `/notices/campaign-check/{version}` are public, tenant-free reads
of the immutable notice (`version/purpose/notice_hash/title/body/published_at/status`). New upload
intent bodies require `notice_version`, strict `notice_acknowledged:true` and
`purpose:"campaign_check"`, separately from `rights_attested`. Missing/false/wrong-purpose is 422;
stale version is `409 NOTICE_VERSION_STALE`. The client reloads the notice and clears only its
acknowledgment, preserving file/caption/rights. Unknown/unloaded notice blocks upload.

Asset/upload/version DTOs expose `authorization_status:active|revoked|legacy_no_notice` and the
`consent_receipt` if one exists. `GET /consent-receipts/{id}` requires current membership;
`POST /consent-receipts/{id}/withdraw` requires admin/marketer and returns the existing deletion
receipt (202), including partial/failed cleanup. Repeats use the same target receipt, never restore
authorization. New attachment/Check/review mutations on legacy sources return
`409 PROCESSING_AUTHORIZATION_REQUIRED`; historical reads and approval revocation remain possible.
New manifests bind the immutable receipt; old hashes/approvals are not rewritten. See
[processing authorization](processing-authorization.md) for the local-only notice boundary.

Implemented contract: [authenticated foundation](authenticated-foundation.md) adds bearer identity
and organization-free membership discovery to `/me/workspaces`. In authenticated mode, content PUT
also requires a bearer token; media bytes use private Storage and deletion may return `partial`
until Storage cleanup succeeds. The existing fixture transport remains development/test only.

Authenticated requests use `Authorization: Bearer <access-token>` and member commands also use
`X-Organization-Id: <uuid>`. `/me/workspaces` needs no organization header and returns active `items`
with `id/name/roles/user`, plus the verified top-level `user`. Fixture headers are rejected in this
mode. The generated OpenAPI declares `SupabaseBearer`; health/readiness remain public. The local
fixture alternative requires its explicit fixture headers and is never an authenticated fallback.

`GET /uploads/{id}/content` rechecks member scope, validated state, tombstones and retention, and
returns private bytes with `Cache-Control: no-store`, `nosniff` and attachment disposition.
Authenticated content PUT requires both bearer scope and `X-Upload-Token`; finalize validates the
actual Storage bytes. Only MP4/WebM, maximum 5,000,000 bytes, are currently supported.

`GET /capabilities` includes `media_processing:{mode,processor_version}` independently from fixture
provider invocation. Finalized media adds `processing_metadata`; versions expose `media_processing`
and `duration_ms`. Decoded metadata includes immutable image/processor identity, measured duration,
dimensions/frame rate/audio presence, normalized hash and an explicit identity source-time mapping.
Missing/unsupported decoding never becomes fixture success. `MEDIA_PROCESSOR_UNAVAILABLE` is safe
503; `MEDIA_VALIDATION_FAILED`/`MEDIA_VALIDATION_TIMEOUT` are 422. A live source processing lease
returns `409 MEDIA_PROCESSING_IN_PROGRESS`. See [media bounds](media-validation.md).

Container cleanup is a declared `local_media_sandbox` deletion destination alongside database and
private Storage. Completion confirms exact source-bound container absence; JSON receipt targets
are never destructive authority. Pending daemon/cleanup failures remain partial, and late decoder
starts cannot recreate a deleted prepared container.

Deletion POST returns a durable receipt: `id/resource_type/resource_id/status/destinations/notice`
and timestamps. `partial` has no completion timestamp; repeating the same scoped target retries
Storage cleanup with the same receipt ID. GET by receipt ID remains scoped. Complete means declared
application destinations were confirmed; it is not a promise of backup or external provider purge.
`GET /deletion-requests?campaign_id=<uuid>` returns up to 50 newest scoped receipts (`items`),
including system expiry receipts, without source excerpts. Omit the campaign filter for the current
organization. Receipt fields additionally expose `requested_by_kind`, `attempt_count`,
`max_attempts`, `retry_after` and `last_error_code`. `in_progress` denotes a leased attempt;
`failed` denotes exhausted automatic retries and is not successful erasure. Explicit authorized
POST retries can recover the same receipt; they do not reset its automatic attempt budget.

Version history includes `source_available`; expired-source captions are blank. New Checks and
review access return `409 RESOURCE_EXPIRED` after the source deadline. Worker input/publication
also checks expiry; cancelled work cannot publish late evidence. The independent local retention
process now erases expired sources/derivatives and reconciles declared Storage copies using the
[anchored cleanup contract](retention-worker.md). Physical cleanup can remain pending/failed.

2026-10-22 implemented contract: finding-decision changes invalidate an existing human sign-off.
Deletion targets both source and local textual derivatives and freezes work for any submission
referencing the deleted source asset. Typed provider output is checked against the campaign's exact
pinned rule pack. PostgreSQL fixture execution now passes the same HTTP contract as SQLite.
Content and finalization capabilities expire after five minutes; expired attempts return
`401 UPLOAD_AUTHORIZATION_EXPIRED`. The streamed content endpoint bounds input to 5 MB before
buffering a complete request.

- Base URL: `http://127.0.0.1:8010/api/v1` by default.
- Identity: local fixture headers `X-Organization-Id` and `X-Fixture-User`; roles are always resolved
  from server-side membership records. `X-Fixture-Roles` is rejected and no request body can grant
  authority.
- Upload: the API issues a short-lived opaque upload/finalize token and an API-local content URL.
  It validates byte length, content type and media signature before creating a submission version.
  Supabase signed Storage URLs are not implemented.
- Async Check: accepted commands return a job status URL. A separate worker publishes only after
  typed evidence/finding validation; retries are bounded at three attempts.
- Invocation mode: only `fixture` is accepted. Recorded/live results cannot be selected or mixed.
- OpenAPI regeneration: `npm run openapi`.

Implemented endpoints are `/me/workspaces`, `/capabilities`, catalog reads, campaign reads/writes,
authorized upload/content/finalize, submission/version reads/writes, Check enqueue/status/result/
comparison, finding decisions, fix-request drafts, review decisions, usage, audit and deletion
requests. The bounded creator foundation also implements member invitation issuance/revocation,
guest exchange, assigned-submission read, guest upload/content/finalize, applicable notice/receipt
and one initial immutable submission version described in section 5. Explicit member-selected
feedback publication, invitation recovery/renewal, later immutable revision and exact-source guest
withdrawal are implemented. Try, dossier, webhook, cancellation, live Track ingestion and
external-delivery routes remain gated. The test-only Track report/intake routes below are implemented.

## 1. Boundary conventions

Application paths use `/api/v1`; provider URLs remain inside adapters. Next.js forwards to the API without duplicating business logic. IDs below are opaque UUIDs, dates UTC ISO-8601, time ranges source milliseconds.

Authenticated tenant routes require a verified member token and an explicit organization context checked against membership. Server derives actor/roles; request-body organization/user IDs never establish authority. GET/POST by ID rechecks parent ownership. Unauthorized cross-tenant IDs return a consistent not-found response. Guest and shopper sessions use their own narrower contracts and cannot call member routes.

Mutating commands with retry/side effects require `Idempotency-Key`. Scope keys by actor/tenant/operation; save a normalized body digest and response reference. Same key/body returns the same accepted/result reference; same key/different body returns 409. Proposed retention at least 24 hours, never shorter than the command's retry window. Durable financial/webhook uniqueness remains after the HTTP key expires. Guest invitation issuance instead uses its explicit client-held `recovery_id`: a retry rotates the unrecoverable secret and revokes the older credential family rather than storing or replaying plaintext.

Use cursor pagination, bounded page sizes and allowlisted sorting. Version-changing commands require an expected version/ETag and fail with 409 when stale. CORS/CSRF/session handling must match the chosen browser auth transport; do not combine cookie auth with an unreviewed wildcard policy.

## 2. Response shapes

Accepted async command:

```json
{
  "operation_id": "opaque-uuid",
  "resource_id": "opaque-uuid",
  "status": "queued",
  "status_url": "/api/v1/jobs/opaque-uuid",
  "invocation_mode": "fixture"
}
```

The UUID strings above are placeholders illustrating shape, not actual records. `invocation_mode` is the selected/tested execution path, never inferred from HTTP success.

Safe error:

```json
{
  "error": {
    "code": "CAPABILITY_POLICY_RESTRICTED",
    "message": "This preview feature is unavailable for the selected eligibility context.",
    "retryable": false,
    "request_id": "opaque-correlation-id"
  }
}
```

Use 400 invalid shape, 401 unauthenticated, 403 forbidden/policy-restricted, 404 missing/inaccessible, 409 stale/conflicting state, 413 too large, 415 unsupported media, 422 invalid domain input, 429 rate/budget limit, 503 temporary provider/capability unavailable. Distinguish rate limits from exhausted budgets by error code and actionable UI. No stack traces, raw provider bodies or private data in errors.

## 3. First-build member surface

| Operation | Input/authority | Result/important guard |
| --- | --- | --- |
| `GET /me/workspaces` | Authenticated user | Active memberships only. |
| `GET /capabilities` | Member and proposed eligibility context | Per-capability status/reason/policy version; configuration is not ready. |
| `GET /products`, `GET /creators`, `GET /rule-pack-versions` | Scoped member; creator filters include product/category/match/permission/verification | Read catalog/tenant-owned curated evidence/applicable packs. Creator evidence exposes source kind/label, permission, verification, method and capture time. First slice uses explicitly synthetic seed intake; authoring and Shopify sync are deferred. |
| `POST /campaigns` | Admin/marketer; brand, name, market, product refs, pinned pack versions | 201 campaign; validate all parent ownership/applicability. |
| `GET /campaigns`, `GET /campaigns/{id}` | Authorized member | Paginated data and current actions; no invented metrics. |
| `GET /campaigns/{id}/readiness` | Authorized member | No-store, deterministic blocker/action/ready summary with tenant-scoped source citations. It does not invoke Wonder or mutate review state. |
| `POST /campaigns/{id}/creators` | Admin/marketer; `creator_id` plus exact `evidence_id` | 201 new roster assignment or 200 identical replay/legacy evidence link. Evidence must belong to the creator and tenant, have recorded permission, be available, and match the campaign product or category. The persisted evidence link is write-once; a different later link returns conflict. |
| `POST /uploads` | Authorized uploader; purpose, proposed type/size, campaign | Scoped signed upload URL/object ID, max bytes, expiration and finalization token. |
| `POST /uploads/{id}/finalize` | Uploader; expected object ref | Queue validation; never trust browser hash/MIME as server-verified. |
| `POST /campaigns/{id}/submissions` | Admin/marketer; validated asset, caption, source rights | 201 logical submission and immutable version. |
| `POST /submissions/{id}/versions` | Authorized uploader; new validated asset/caption | New version; previous current review superseded transactionally. |
| `GET /campaigns/{id}/submissions`, `GET /submissions/{id}` | Scoped member | Submission list, immutable version history, current review contexts and authorized media refs. |
| `POST /submission-versions/{id}/checks` | Admin/marketer; applicable pack versions, capability mode | 202 check/job after budget reservation; missing keys/policy don't become fake live success. |
| `GET /checks/{id}` | Permitted member | Manifest, coverage, three Check states, findings and provenance. |
| `GET /checks/{id}/comparison` | Permitted member; `previous_check_id` in same submission | Added/persisted/resolved/incomparable findings; changed rules/models and failed evidence make affected comparisons incomparable, not automatically fixed. |
| `POST /findings/{id}/decisions` | Reviewer; decision, rationale, expected review version | Append finding decision; accept/dismiss/incorrect/uncertain, never auto-approve content. |
| `POST /checks/{id}/review-decisions` | Reviewer; action, exact manifest hash, expected review version, rationale | Atomic approve/reject/request_changes/revoke where allowed. |
| `POST /checks/{id}/fix-request-drafts` | Reviewer/marketer; selected findings | Draft only; no external message sent. |
| `POST /checks/{id}/creator-feedback` | Admin/marketer/reviewer; exact draft ID, selected message, optional paired millisecond range, required actor-scoped idempotency key | 201 immutable creator-visible snapshot or 200 identical replay. Requires the current non-superseded version, active processing authorization and completed/partial Check; stores exact invocation/status/manifest provenance and sends nothing externally. |
| `POST /campaigns/{id}/guest-invitations` | Admin/marketer may target a new empty or existing matching submission; reviewer may target only an existing matching submission; client supplies a UUID `recovery_id` | Implemented locally: new scoped invitation; retrying the same recovery/scope rotates all prior family credentials; returned secret is shown once and never logged; no automatic external sending. |
| `POST /guest-invitations/{id}/revoke` | Authorized issuing role in same tenant | Implemented locally: revoke the complete renewal family and every session. |
| `POST /guest-invitations/{id}/renew` | Original issuing member with a currently qualifying role | Implemented locally: issue a new grant in the immutable scope and atomically revoke every older grant/session; never silently extend or replay a lost secret. |
| `GET /checks/{id}/review-summary` | Authorized member | Readable provenance summary; later PDF uses same data/permissions. |
| `GET /jobs/{id}` | Job-scoped member | Canonical job state, safe stage progress, result refs and retry guidance. |
| `POST /jobs/{id}/cancel` | Initiating writer or admin with explicit cancellation authority; job cancellable | Acknowledged intent; in-flight spend may still need reconciliation; Viewer cannot cancel others' work. |
| `POST /campaigns/{id}/dossiers` | Explicit `run_dossier` grant to admin/marketer/reviewer, never Viewer; bounded evidence scope and budget | 202 Wonder operation; snapshot IDs validated, no autonomous actions. |
| `GET /dossiers/{id}` | Authorized member | Summary, validated record citations, gaps, provenance and stale status. |
| `GET /campaigns/{id}/track` | Authorized member; window/filter | Defined event/order counts, freshness, attribution confidence/method and test/live separation. |
| `POST /campaigns/{id}/track/test-events` | Admin/marketer; creator on campaign roster | Idempotent test click/order/refund event. Stable external IDs, currency and refund bounds are enforced; no live event can enter this route. |
| `POST /guest/consent-receipts/{id}/withdraw` | Active scoped guest session; exact receipt source belongs to that invitation renewal family and assigned submission | Blocks the exact source, revokes authorization with guest attribution and returns the durable deletion receipt. No generic source traversal or direct Storage delete. |
| `GET /usage` | Admin or permitted user | Actual units, estimated/known costs, held budget and plan caps. |
| `POST /deletion-requests`, `GET /deletion-requests/{id}` | Owner/admin or a separately scoped personal-data requester | 202 request and per-destination receipt; no raw blob ID authority. |

The fixture transport uses the two headers documented above. Production member auth remains
Supabase JWT plus explicit organization scope. Changing transports cannot change authorization
invariants. Admin does not imply reviewer unless reviewer authority is explicitly granted.

## 4. Check payload contract

The implemented check path is scoped by submission-version route ID and the campaign's pinned rule
pack. It accepts `scenario`, literal `invocation_mode: fixture`, and literal
`schema_version: check-result.v1`. The server creates an immutable manifest with content/caption,
rule, prompt, model and schema versions; callers cannot override provider identifiers or secrets.

Check result includes `analysis_status`, `machine_assessment`, `review_status`, `manifest_hash`, `required_coverage`, `observed_coverage`, `missing_intervals`, `findings`, `model_call_summaries` and result timestamps.

Each finding has ID, rule ID/version, severity (`critical|major|minor`), evidence IDs/source, optional source time range or caption span, timing precision, short evidence text, uncertainty/confidence provenance and suggested action. A model score is not a calibrated probability.

A review decision body includes `action`, `expected_review_version`, `manifest_hash` and `rationale`. Server revalidates current revision, complete analysis, permissions and unresolved required blockers in the same transaction as the approval. Return 409 `REVIEW_CONTEXT_CHANGED` for a racing finding/reupload, and 422 `REQUIRED_REVIEW_INCOMPLETE` for unresolved gates. The approval response is not a publication instruction or legal certificate.

`GET /checks/{analysis_id}/approval-report` returns a strict `approval-report.v1` read model only
while that exact review context is currently approved. It binds the approved submission version,
manifest/media/caption hashes, reviewer and rationale, rule/prompt/model/schema versions, coverage,
evidence, finding decisions and explicit limitations. The route is tenant-scoped and `no-store`;
unapproved, revoked, superseded, deleted or incomplete records do not produce a report. The client
renders the response as a readable Markdown download, not a compliance certificate.

## 5. Creator guest contract

Accepted by ADR-029. A bounded local initial-draft slice is implemented and verified as of
2026-10-28: member invitation issuance/revocation/recovery/renewal, fragment-token exchange,
cookie-session resume, allowlisted assigned-submission read, guest-attributed upload/content/finalize,
applicable immutable notice/receipt, one initial immutable version and explicit member-selected
feedback publication. The [creator portal contract](creator-portal.md)
specifies the remaining revision and withdrawal/deletion traversal. Generated
OpenAPI remains the authority for the implemented surface.

Invitation creation is a member command scoped to a single campaign/rostered creator/submission and
allowed actions. Admins/marketers may create an empty assigned submission or target an existing
matching submission; reviewers may target only an existing matching submission. The invitation URL
holds at least 256 bits of random capability-secret entropy in its fragment. Show it once, store only
its SHA-256 digest, prevent referrer/log leakage, and expire the grant after 48 hours.

`POST /guest/exchange` transactionally consumes the invitation token and issues a scoped 30-minute
guest session in an HttpOnly, SameSite=Strict cookie; its authority cannot outlive the grant.
Expired, consumed, revoked and rate-limited tokens fail uniformly. The implementation limits
attempts to 10 per 15-minute privacy-minimized client bucket and five per 15-minute presented-token
digest bucket. Blocked buckets do not create more attempt rows, and the retention process alone
prunes records after 24 hours. Replay, simultaneous two-connection exchange, expiry, revocation,
recovery and issuer-authority loss are locally tested. A deployment-specific trusted-proxy/client-
bucket contract remains a hosted release gate.

`GET /guest/submission` is the implemented guest data read. It rechecks the session, grant,
issuer authority, assigned scope and source availability, then returns an allowlisted view of that
one submission. It cannot enumerate members, other creators, rule administration, billing or
unrestricted assets. The isolated `/creator` entry removes the fragment before effects and resumes
the scoped cookie session; local desktop/mobile browser verification is recorded in the ledger.

Guest `GET /guest/notices/campaign-check`, `POST /guest/uploads`,
`PUT /guest/uploads/{id}/content`, `POST /guest/uploads/{id}/finalize` and
`POST /guest/submission-versions` are implemented for the empty assigned-submission milestone.
They enforce stored scope through the separate non-BYPASSRLS `vouch_guest` pool, at most five
atomically reserved sources and 25,000,000 reserved bytes, and a five-minute upload/finalize
window. Media is API-proxied through an exact-object-key Storage adapter with its own server-only
credential. Finalization validates the guest-owned staged object and records a guest-attributed
receipt. Version publication requires idempotency and currently rejects any non-empty/current
submission with `GUEST_REVISION_NOT_AVAILABLE`. Feedback is published only by an explicit member
command and appears in the allowlisted guest read with its version number, selected text/range,
invocation mode, analysis status, manifest hash, publication time and current/historical label.
Internal findings, rationales and draft discussions are not exposed. Withdrawal remains design-only.
Member recovery/renewal creates a new grant, preserves the immutable capability set and consumed
quota maxima, and revokes the old family atomically; the guest cannot self-extend a grant.

A validated content `PUT` is replay-safe only inside the still-active guest session, grant and
five-minute upload capability. If that upload already holds the same server-measured SHA-256 digest
and byte length, the API acknowledges the retry without another Storage write and without moving
the source back to an earlier state. Different bytes or length conflict; a retry never replaces an
accepted object. In Supabase mode the service holds the tenant-lineage and exact-source database
locks through the bounded private Storage write, so member deletion cannot complete before a late
object appears. An ambiguous Storage failure rolls back the database transaction; an exact-key
retry reconciles the remote object before deciding whether another write is required.

Grant/session expiry removes portal authority only. It does not revoke an already valid processing
receipt, erase accepted media, free unconfirmed cleanup bytes or reset/extend the source's anchored
retention deadline. Withdrawal and erasure remain explicit, source-scoped lifecycle operations.

## 6. Shopper Try contract

These routes use a signed, server-created campaign/creator/product entry link plus a short-lived scoped session. They are not anonymous general image-generation endpoints.

| Operation | Contract |
| --- | --- |
| `POST /try/sessions` | Validate entry context and operator/deployment/end-user eligibility; return capability state and approved notice versions before accepting photos. |
| `POST /try/sessions/{id}/consent` | Save explicit purpose/notice/provider consent and adult/photo-use attestation; decline ends photo intake. |
| `GET /try/sessions/{id}/products`, `PUT /try/sessions/{id}/product` | Return only eligible campaign products; selection checks expected session version. During processing, reject a switch with 409 until cancellation/new session; never silently change an in-flight preview. |
| `POST /try/sessions/{id}/photo-uploads` | Require active eligible consented session; return narrow signed upload instructions, not public bucket access. |
| `POST /try/sessions/{id}/photo-uploads/{upload_id}/finalize` | Scoped session/object validation, byte/MIME/hash checks and quarantine; no preview from an unvalidated object. |
| `POST /try/sessions/{id}/previews` | Finalized validated photo, immutable product version, operation key and budget; 202 operation. |
| `GET /try/sessions/{id}` | Scoped status, safe guidance, private eligible result and deletion deadline. |
| `POST /try/sessions/{id}/cancel` | Stop new work/delivery; return actual cancellation state. |
| `DELETE /try/sessions/{id}/media` | Revoke future access/delivery immediately, queue per-destination cleanup, return receipt reference. |

Consent decline moves the session to `cancelled` with reason `consent_declined`; no photo accepted and no provider work scheduled. Product selection moves an active consented session to `awaiting_photo`; changing a product invalidates the current preview context and requires a new explicit preview command. Retained photo reuse requires consent scope and the original unexpired retention deadline; product switching/retry never extends it.

A concurrent delete/cancel invalidates future result publication even if the provider finishes. Publication/outbox writes atomically assert the current session version and no tombstone; the delivery dispatcher serializes its handoff against cancellation/deletion. Already handed-off remote delivery cannot be guaranteed retractable and must be disclosed. One generation retry means at most two generation attempts for one logical photo/product operation; separate transport retries cannot silently exceed that ceiling. Unknown provider outcomes require reconciliation.

Return policy-restricted before photo upload when Muse Image is ineligible. Web fallback changes the channel, not model-region eligibility. No photo is automatically routed to another vendor.

## 7. Provider ports and call envelope

Five logical ports: `Reasoner`, `Transcriber`, `Segmenter`, `TryOnProvider`, `CampaignDossier`. Dossier can reuse reasoning transport but has a narrower product contract. The exact provider payload, SDK version, schema flags and stream parser live in adapters; see [verified public surfaces](../integrations/meta-api-readiness.md).

Every call envelope carries tenant/job/logical operation, capability, immutable input refs, data classification, consent/policy decision, requested model, prompt/schema/adapter versions, invocation mode, deadline and budget reservation. Every result carries actual provider/model, request ID when available, typed outcome/coverage, usage units and pricing provenance, timings and remote artifact cleanup refs.

The Check worker persists this lifecycle in tenant-scoped `model_calls` rows for each Transcriber,
Segmenter and Reasoner attempt. Fixture rows are known-zero-cost and returned as provenance
summaries. `OUTCOME_UNKNOWN` is terminal, is not automatically retried, and leaves the reservation
held for explicit reconciliation. Live product adapters remain disabled.

Normalize errors to `NOT_CONFIGURED`, `ACCESS_UNVERIFIED`, `ACCESS_DENIED`, `POLICY_RESTRICTED`, `SAFETY_BLOCKED`, `INVALID_INPUT`, `RATE_LIMITED`, `BUDGET_EXCEEDED`, `TIMEOUT`, `PROVIDER_UNAVAILABLE`, `INVALID_PROVIDER_OUTPUT`, `CANCELLED`, plus `OUTCOME_UNKNOWN` for uncertain paid side effects. A regional policy block maps to `POLICY_RESTRICTED` with a safe reason. `TIMEOUT` is retryable only when the side effect is known absent or verified safe; ambiguous paid outcomes retain their reservation until reconciliation. API translates these into stable user-safe codes.

Provider output is data: schema validation is followed by rule/source ID, timestamp, scope and privacy validation. Store untrusted payloads only in authorized retained artifacts when needed, never in broad logs. Fixture providers must implement success and failure contracts, not always-success placeholders.

## 8. Webhooks, tracking and future surface

Provider webhooks use separate `/webhooks/{provider}` paths and raw-body signature verification. Verification challenges are distinct from authenticated events. Persist the inbox receipt and job/outbox scheduling intent in the same transaction before acknowledging; retries/reordering are normal. Test/live installation mapping cannot be chosen by the external payload alone.

`GET /r/{code}` resolves a server-stored, allowlisted destination; it is not an open redirect. Record a privacy-minimized click and preserve a server-authorized tracking context through permitted checkout integration. Rate-limit abusive links and avoid raw IP/user-agent retention unless necessary under the notice.

Attribution v0, conflicts, refunds, test flags, currencies and proposed seven-day linkage window are defined in [data model](data-model.md#7-attribution-policy-v0). A simulator can exercise orders before Shopify access but is visibly labeled and never counted as live revenue.

Deferred contracts: OAuth/install/token rotation, social discovery search, outbound sending, audit PDF, billing, public customer API/webhooks, live monitoring. Add each only with permission scopes, real account verification, retention, failure/retry and acceptance tests. Do not expose a broad generic `/auth/*` or unconstrained model-proxy endpoint as a placeholder.
