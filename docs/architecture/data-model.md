# Domain and data model

Status: shared runtime model on SQLite and Supabase Postgres, updated 2026-10-28. The private
`vouch` runtime schema is generated from SQLAlchemy metadata and owned by additive migrations;
the earlier `public` prototype is preserved with authenticated reads only. The model includes the
locally verified creator invitation/exchange/session boundary, guest upload/content/finalize,
guest-attributed receipt, initial/later immutable versions and explicit creator-feedback publication.
Exact-source guest withdrawal is implemented. See
[implementation status](../engineering/implementation-status.md) and [API contracts](api-contracts.md).

### Implemented persistence modes

The accepted [storage allowance contract](oauth-storage-motion.md) derives capacity from existing
tenant media assets and exact asset-bound cleanup confirmations rather than introducing a second
ledger. Pending/unknown uploads reserve the bucket's entire 5,000,000-byte per-file maximum;
accepted immutable bytes count at their actual size. Tombstoned Storage objects remain pending
until their own Storage destination is confirmed absent. An unrelated receipt or successful
sandbox-only deletion cannot release object capacity. This adds no approval/hash rewrite or new
storage copy. Expired unconfirmed intentions remain reserved until cleanup proves absence.

Implemented changes are specified in [authenticated foundation](authenticated-foundation.md):
`users.auth_subject` (unique, bootstrap-owned), media `storage_backend`/`object_key`, and separate
API/worker grants plus transaction-local RLS context. Additive migrations preserve existing state.

Decoded media adds immutable `processing_metadata` (measured timeline/processor/image/hash) and
two server-only lifecycle fields: `processing_container` and `processing_lease_until`. Prepare an
empty scoped container before committing that reference; byte processing can only start the stored
run. Deletion includes its confirmed absence. These runtime fields are not mutable analysis inputs;
new manifests bind the immutable metadata, while legacy empty metadata preserves old bindings.

`consent_receipts` has one tenant-scoped receipt per asset: campaign, verified uploader, purpose,
immutable notice version/hash and UTC acceptance time, plus irreversible revocation time/actor/
reason. Tenant composite keys bind the source and actor; API insert requires its pending source.
Check workers read only their job source's receipt; retention can revoke only the exact deleted
source it is scrubbing. No direct browser grant and no legacy backfill. New manifests include
`processing_authorization:{receipt_id,purpose,notice_version,notice_hash}`; historical hashes stay
unchanged. Asset/version DTOs classify `active`, `revoked` or `legacy_no_notice` and expose the
receipt when present. See [authorization cutover](processing-authorization.md).

The creator slice adds digest-only `guest_grants`, scoped `guest_sessions` and
privacy-minimized `guest_exchange_attempts`, with a separate non-BYPASSRLS guest role/pool and
24-hour retention-worker pruning. Grant rows carry a non-secret issuance recovery UUID and immutable
renewal-root scope; recovery or explicit renewal creates a new digest and atomically revokes the
older family while preserving action scope and consumed quota maxima. Blocked client/token buckets
stop inserting attempt rows. Guest-owned upload intents/assets, guest-attributed processing receipts,
idempotent commands and one initial immutable submission version are implemented. A validated
content replay is accepted only for the same server-measured hash and byte length and cannot
rewrite Storage or regress source state. The Supabase path retains tenant-lineage and exact-source
locks through the bounded private Storage write; ambiguous failures roll back for exact-key remote
reconciliation. Feedback, subsequent immutable revision and exact-source guest withdrawal are
implemented. The hosted
trusted-proxy/client-bucket contract remains release work.

| Mode | Purpose | Source of truth | Verification |
| --- | --- | --- | --- |
| `fixture-sqlite` | Fast local API/worker workflow | `services/backend/src/vouch_backend/models.py` plus additive SQLite compatibility | Default no-network tests; counts in execution ledger |
| `supabase-local` | Real local Auth/Storage, same fixture-provider workflow | Initial private runtime DDL plus additive authenticated migrations | Restricted-login integration, SQL assertions, guest role/session isolation, guest upload replay and deletion-race coverage, and desktop/mobile browser tests; counts in execution ledger |
| `recorded` / `live` | Future provider execution over the production persistence path | Durable `model_calls` envelope is implemented; live adapters remain disabled | No product-call claim |

The original public prototype no longer defines the application runtime. Its migration and seed are
retained for traceability; private `vouch` tables hold actual workflow state. RLS and privilege tests
deny direct browser access to runtime tables. Auth subjects are unique and provisioning-owned.
Authenticated media records hold a deterministic object key, not duplicate bytes; fixture records
retain database byte storage. Deletion receipts persist pending destinations and can be retried.
Local bounded decoding and anchored retention are implemented. Hosted bootstrap, malware scanning
and production process isolation remain deployment gates.

## 1. Global conventions

Use UUID IDs, UTC timestamps, explicit schema/version metadata and immutable source references. Every tenant-owned row has a non-null `organization_id`; parent relationships use composite foreign keys such as `(organization_id, campaign_id)` to prevent cross-tenant references. Enforce RLS and API/worker scope checks, not just a client-side filter.

Use integer milliseconds for source timelines: `0 <= start_ms < end_ms <= source_duration_ms`. Caption-only evidence has null time ranges plus character spans; unknown timing stays null. Keep source-to-derived mappings for transcoded/chunked/sampled media and a timing precision/coverage field.

Money uses fixed decimal with currency for model costs, integer minor units plus currency for orders. No floating-point currency or invented conversion rate. Nullable unknown cost is different from zero. Text, IDs and hashes can remain personal data.

## 2. Entity inventory

| Domain | Records and essential fields | Invariant |
| --- | --- | --- |
| Workspace | `organizations`; `memberships` (user_id, active); `membership_roles` (membership_id, role); `brands` | Membership unique per user/organization; roles are explicit grants and can coexist. Admin does not implicitly grant Reviewer. One tenant can hold several brands; brand-restricted permissions are a later explicit feature. |
| Catalog | `products` (brand, external ID, category); immutable `product_versions`; asset refs | Preview uses the exact product snapshot, not a moving catalog row. |
| Campaign | `campaigns`; `campaign_rule_pins`; `campaign_creators` (optional write-once `evidence_id` for legacy compatibility) | Applicable pack versions pinned; roster unique per campaign/creator; a Find-added creator binds compatible tenant evidence that cannot later be rewritten. |
| Content specification | `product_claims`; `campaign_requirements` | Claims bind wording to product evidence and optional expiry. Requirements bind typed expectations to a campaign; assessments are derived from the current immutable caption/Check evidence and are not approvals. |
| Creator | `creators`; `creator_evidence` (source kind/URI/label, product/category match kind, permission/license, timestamp, verification and collection mode) | No assumed permission from a public URL; exact product and category relevance remain distinct; no cross-tenant creator intelligence by default. |
| Submission | `submissions`; `submission_versions` (asset_id, media hash, caption text/hash, uploader, version_no) | Versions append, never overwrite; uniqueness on submission/version number. |
| Media | `media_assets` (private object key, kind, parent_asset_id, hash, bytes, validated MIME, duration, retention_deadline, deletion state) | Only server-validated finalized objects can enter a model pipeline. |
| Rulebooks | `rule_packs`; immutable `rule_pack_versions`; `rules` with sources/applicability/status | Draft and legally reviewed are distinct; activation requires authorized human action. |
| Analysis | `analyses` (submission_version, manifest_hash, analysis_status, machine_assessment, coverage, completed_at) | Manifest immutable; required evidence gaps prohibit a clean assessment. |
| Evidence | `evidence_items` (analysis, modality, artifact ref/span, source time range, precision, missing intervals) | Every cited fact resolves to authorized evidence in the same analysis/snapshot. |
| Findings | `findings` (analysis, rule_version, severity, evidence_ids, time/span, suggestion, uncertainty); `finding_decisions` | Original model finding immutable; reviewer decisions append with rationale. |
| Review | `review_contexts` (analysis, submission_version, current state/version); `review_events`; `approvals` | Approval bound to exact manifest and decisions revision; no silent carry-forward. |
| Creator access | `guest_grants` (token digest, immutable scope/recovery family, expiry, consumed/revoked state and upload quotas); `guest_sessions`; `guest_exchange_attempts`; `guest_commands`; guest actor branches on assets/receipts/versions | Transactional invitation exchange is single-use; simultaneous callers yield one session; member recovery/renewal revokes older credentials without resetting consumed quota. Sessions cannot enumerate workspace data or self-renew. Initial upload/version writes remain inside the assigned submission and true guest actor lineage. Validated content replay requires the same measured digest/length; tenant-lineage plus exact-source locking fences the Supabase write against deletion. |
| Try | `try_sessions` (campaign/creator/product version, state, capability decision, consent, deadline); `try_attempts` | One bounded generation retry; session version and tombstone checked before delivery. |
| Consent | `consent_receipts` (purpose, notice version, actor/pseudonym, timestamp, revocation) | Consent is purpose-specific; never a blanket training license. |
| Integration | `integrations` (provider, external account, environment, encrypted credential reference); `capabilities`; `eligibility_decisions` | Credentials server-only; account/region readiness differs per capability. |
| Work | `jobs`; `job_stages`; `idempotency_records`; `webhook_inbox`; `outbox` | Durable intent, dedup, leases/fencing and retries explicitly represented. |
| Spend | `budget_periods`; `budget_reservations`; `model_calls`; `usage_ledger` | Runtime persists one tenant/job/stage/attempt envelope with pinned versions, status, request-ID/usage/cost fields and timings. Fixture calls record known zero cost. Paid work still requires atomic reservation and reconciliation. |
| Cleanup | `provider_artifacts` (remote ID, region/provider, expiry, deletion status); `deletion_requests`; `deletion_items`; tombstones | Every local/remote derivative has ownership and a cleanup path, including failed jobs. |
| Tracking | MVP `outcome_events`; later `tracked_links`, webhook inbox and connector-owned order projections | MVP accepts only roster-bound `test` clicks/orders/refunds with stable external IDs, attribution provenance and currency. Test/live summaries are separate. Live connector ingestion remains deferred. |
| Dossier | `campaign_dossiers` (snapshot hash, evidence IDs, prompt/model, gaps, result artifact) | Read-only output; source IDs validated against tenant snapshot. |
| Audit | `audit_events` (actor, action, resource/version, time, safe metadata, chain/checkpoint refs) | Append-only application path, limited retention; never claim invulnerable immutability. |

Large transcripts, extracted frames and full model payloads belong in restricted retained artifacts when needed, not general audit/analytics JSON. Keep minimum short evidence excerpts in findings and make erasure/redaction possible under the agreed policy.

## 3. Canonical state vocabularies

| Field | Values |
| --- | --- |
| `analysis_status` | `queued`, `running`, `completed`, `partial`, `failed`, `cancelled` |
| `machine_assessment` | `no_issues_detected`, `fixes_suggested`, `potentially_blocking`, `human_review_required`, `not_assessed` |
| `review_status` | `unreviewed`, `changes_requested`, `approved`, `rejected`, `superseded`, `revoked` |
| `job_status` | `queued`, `running`, `retry_wait`, `succeeded`, `failed`, `cancelled`, `dead_letter` |
| `try_session_status` | `awaiting_consent`, `awaiting_product`, `awaiting_photo`, `processing`, `ready`, `failed`, `cancelled`, `expired`, `deleting`, `deleted` |
| `capability_status` | `not_configured`, `awaiting_access`, `policy_restricted`, `configured_unverified`, `ready`, `degraded`, `disabled` |
| `invocation_mode` | `fixture`, `recorded`, `live` |
| `deletion_status` | `requested`, `in_progress`, `partial`, `completed`, `failed` (automatic retries exhausted, still incomplete) |

Cache hit/freshness, environment (`development`, `test`, `staging`, `production`) and channel/provider provenance are separate fields. A cached original live result retains its run time; recorded replay does not become fresh live work. Test-mode Shopify orders remain test data even if the webhook was delivered live.

Local retention implementation adds nullable `deletion_requests.requested_by` plus
`requested_by_kind` (`member`/`retention`), attempt/max-attempt counts, retry time, lease owner/time,
fence and safe error code. System expiry receipts have no human actor. The same row is the durable
cleanup outbox; retries never create another source deadline. Existing member receipts retain
attribution. PostgreSQL uses additive migration; legacy SQLite upgrades copy the receipt table
transactionally with row/index/trigger/FK preservation and rollback proof. See
[retention authority and ordering](retention-worker.md).

## 4. Check transitions and immutable review context

Continuation contract, 2026-10-22: a new disposition on an already decided review context records an
invalidation and returns the context to `unreviewed`; historical approvals remain audit records but
cannot appear as current authorization. Submission and source-asset deletion erases local text
derivatives (captions, evidence, findings and fix-request drafts), cancels/fences related jobs, and
retains only opaque version/hash/audit and deletion receipts needed for integrity.

Analysis moves queued → running → completed/partial/failed/cancelled. A retry resumes or replaces an orchestrated attempt; published analysis snapshots never change under an existing approval. A new analysis or revision gets a new ID.

The analysis manifest includes content and caption hashes, product/context snapshot, applicable rule-pack/rule versions and hashes, prompt/schema/adapter versions, requested and returned model IDs, media-transform/time-map versions, evidence coverage and invocation mode. The review context also binds the current finding-decisions revision. Do not attach an approval merely to a mutable campaign or filename.

Only an authorized reviewer can move a current unreviewed/changes-requested context to approved or rejected. Approval requires completed analysis, supported applicable pack, resolved required blockers/gaps and current expected revision. Approving while findings change must fail a compare-and-swap transaction. A reviewer can dismiss a false finding with rationale; required policy blockers cannot be bypassed through a generic admin flag.

A new content/caption version supersedes the former context for the current campaign view, without deleting its historical approval event. Explicit revocation appends a reason and actor. A new rulebook does not retroactively rewrite old history; mark affected current assessments stale and require recheck according to the agreed campaign policy.

## 5. Work and budget concurrency

A job stores type, tenant, resource/snapshot ref, attempt count, deadline, retry_after, lease_owner, lease_until and monotonically increasing fencing token. A worker claims in a short transaction and performs I/O outside it. Completion requires the active fence; a stale worker cannot publish or deliver.

A logical paid operation is unique by tenant, stage/input snapshot and operation key. Track requested, in-flight, succeeded, failed and outcome-unknown provider attempts. Never assume cancellation/timeout means no charge. Provider operation IDs/idempotency are used only where verified; ambiguous requests are reconciled before retrying an expensive side effect.

Reservation transaction locks the organization's current budget row, verifies `settled + held + proposed <= cap`, and adds a unique reservation. These buckets are disjoint: held includes the conservative remaining exposure of every in-flight or unresolved paid attempt, even after cancellation or lease expiry. Settled exposure moves out of held atomically; do not count it twice. Release only the known unused part after reconciliation. Team-wide model limits are separate from tenant caps. Price snapshots are versioned; changed prices don't rewrite historical usage. Unknown usage blocks automatic spend reconciliation rather than becoming zero.

An inbox unique key is `(provider, integration_id, provider_event_id)`; store a body digest and reject a conflicting replay. If a provider supplies no reliable event ID, document a verified event-specific dedup scheme before activation. Outbox uniqueness uses the domain action ID, not just message text.

## 6. Regional and data lifecycle decisions

Eligibility records include capability/provider/model, policy version, operator/access location, deployment/processing location, end-user location, evidence provenance, decision and reason. A restricted or unknown required dimension denies that capability. Do not derive permission solely from selected locale, phone country or IP.

Proposed retention defaults: Try source and all derivatives up to 24 hours from original receipt; Check source and derived media 30 days from upload; findings/review/consent metadata 90 days for the pilot; operational metadata 30 days. These are not statutory periods. Customer agreement, counsel and actual provider/backup capabilities must resolve final periods before real users. See [privacy policy design](../security/privacy-and-threat-model.md).

Deletion freezes new work, revokes scoped access and writes a tombstone. Delete/retry each destination; publication writes and outbox creation must atomically assert the current version and absence of a tombstone in the same transaction, rather than checking then writing later. A remote call already in flight may complete; register its artifacts for cleanup without publishing them. External sends cannot be recalled reliably, so serialize the final delivery handoff against cancellation/deletion and disclose any already handed-off copy. Store per-destination confirmation and remaining limits. `completed` requires completion of the declared deletion scope, not an assumption about unknown provider/security retention. Restore replays tombstones before reopening traffic.

Local creator invitations expire after 48 hours and exchange once for a 30-minute scoped session.
Guest upload/finalize authority of at most five minutes is implemented; sensitive read URLs of one
minute remain proposed. Member-only recovery/renewal is implemented without retaining plaintext secrets. Capability expiry is not the retention deadline;
extending/retrying a session never extends a photo's original deletion deadline.

## 7. Attribution policy v0

All events include tenant, environment, source, occurred_at and received_at; creator/campaign/product references are verified, not accepted from unauthenticated arbitrary IDs.

1. Upsert an order only after verified integration receipt and stable external order ID. Preserve order currency and provider test flag.
2. A unique campaign creator discount code wins only if it maps unambiguously to one eligible roster assignment.
3. Otherwise use a verified checkout-linked tracking identifier created by Vouch and preserved through the checkout integration, with a proposed seven-day click-to-order window.
4. If code and tracking conflict, or multiple creators match, mark `ambiguous` and preserve evidence; do not guess or apply an invisible last-click rule.
5. Without sufficient evidence mark `unattributed`. Raw UTM on a landing URL alone is not evidence the eventual order belongs to that visitor.
6. Refund/cancellation adjustments update net attributed order value once per external adjustment ID. Never erase historical order events or count duplicate deliveries twice.

Model output never changes attribution or commission. First release reports attributed outcomes, not causal lift, final payouts or audited revenue. Add-to-cart is displayed only when an authorized source actually supplies it. Denominators, currencies, refunds, test/live scope and window are explicit in reports.

## 8. Initial indexes and migrations

Index tenant plus parent/time on campaign, submission, analysis, findings and tracking reads; unique memberships/roster assignments; unique input versions; inbox/outbox operation keys; provider call logical keys; external order/refund IDs; active job queue selection by status/retry_after/lease; retention/deletion deadlines. Validate actual query plans before speculative indexes.

The runtime model includes composite tenant foreign keys, explicit organization scope on roles and
unique tenant/parent relationships. The public prototype's former direct-write policies are removed
by an additive migration. Current pgTAP coverage checks tenant reads, revocation, role resolution,
denied mutation paths, private runtime isolation, single-use guest exchange and separate guest-role
read isolation. A real two-connection authenticated test proves single-consumption under simultaneous
exchange, and SQL tests prove bounded attempt writes. Restricted authenticated tests cover guest
media mutation, notice/receipt attribution, quota reservation, exact-byte replay and the Supabase
upload/deletion fence. `creator_feedback` binds one tenant/submission/version/analysis/fix-draft
snapshot to the publishing member, actor-scoped idempotency key and immutable Check provenance.
Publication requires the current non-superseded review context, completed/partial analysis, active
processing receipt and a validated live source; optional ranges must fit measured duration. Source
erasure clears the creator-visible message/range while retaining minimal lineage and provenance.
Production worker/Storage credentials and hosted deployment remain release gates; later creator
revision and exact-source guest withdrawal are implemented.

The shared runtime implements organization scoping, server-derived roles, immutable
submission versions, analysis/review state separation, approval binding, tombstones, idempotency,
budget reservations and audit events. It is not a substitute for the missing production credential
path. `vouch-db-schema` emits deterministic PostgreSQL DDL for review; apply schema evolution through
additive CLI migrations instead of `create_all` on Postgres. Existing SQLite files receive the
additive role-scope column without deleting user data.
