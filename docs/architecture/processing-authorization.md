# Versioned processing authorization

Date: 2026-10-23. Status: implemented and verified locally; command evidence is in
[implementation status](../engineering/implementation-status.md#authorization-continuation-2026-10-23).
This advances TRUST-03 after [media validation](media-validation.md). It is not legal review or
proof that every depicted person consented. Provider execution remains fixture-only.

## Notice and intake

Publish an immutable server-owned `campaign_check` notice: version, SHA-256, purpose, body,
publication date and `draft_local_only` status. Its text explains fixture processing, optional
decoded media, 30-day anchored source retention, source/derivative cleanup and backup/provider
limitations. No ZDR, no-training, lawful-basis or universal-erasure guarantee. Current/versioned
notices are public and contain no tenant data; prior versions remain readable.

Every new upload intent requires a separate affirmative notice acknowledgment, exact current
`notice_version` and `purpose=campaign_check`, in addition to rights attestation. No silent defaults
or fixture exemptions. Missing/false/wrong-purpose requests fail validation; a stale version returns
`409 NOTICE_VERSION_STALE`. The UI preserves the draft but reloads the notice and clears its
acknowledgment after a stale-version error. Unknown/unloaded notice blocks intake.

Create `consent_receipts` atomically with the upload: tenant, asset, campaign, verified member,
purpose, immutable notice version/hash, accepted time, optional revoked time/actor/reason. This is
the workspace member's processing authorization acknowledgment, not third-party subject consent.
One receipt per asset. New analysis manifests bind receipt identity/version/hash. Keep provider
and media modes independently visible.

This draft notice authorizes only the documented local fixture-provider purpose. It is not an
activation approval for live Meta processing. Live integration needs verified terms, an appropriate
notice/version and any required renewed authorization before real provider uploads or calls.

## Withdrawal, expiry and authorization

Expose scoped receipt reads and an explicit admin/marketer withdrawal command. The selected
asset shows notice provenance and a deliberate “Withdraw authorization and delete” confirmation.
Withdrawal uses the existing lineage-locked source erasure, Check fencing, budget release and
per-destination cleanup receipts. Revocation and durable erasure intent are one transaction; retry
cannot reactivate authorization or extend retention. Other deletion/expiry paths also mark the
linked authorization revoked with a truthful source-deleted/expired reason and system attribution
where appropriate. A pending/failed cleanup receipt is never successful physical deletion.

API has only member-scoped insert/read and irreversible revocation grants. Check worker may read
the job source's receipt but never issue/revoke one. Retention can read/revoke only its scoped
deleted source's receipt and cannot manufacture an acknowledgment. Direct browser table access
stays denied. Creator-guest and self-service privacy-rights requests remain a separate boundary;
the local application must not present this role-limited command as universal rights fulfillment.

## Cutover and compatibility

Do not backfill fabricated receipts. Existing assets are explicitly `legacy_no_notice` and retain
their historical hashes/approvals as read-only provenance. New attachment, Check processing and
new human sign-off require a fresh acknowledged upload; old queued work without authorization
cancels rather than publishing. Historical GETs remain available under existing source/tenant
retention guards. Reupload creates a new immutable asset/receipt/version; changing a notice never
rewrites a historical manifest or approval.

## HTTP contract

- `GET /api/v1/notices/campaign-check` and `.../{version}`: public immutable notice.
- Upload intent adds mandatory `notice_version`, `notice_acknowledged=true`,
  `purpose=campaign_check`; the response/asset/version identifies its receipt/classification.
- `GET /api/v1/consent-receipts/{id}`: current member-scoped receipt, no other tenant discovery.
- `POST /api/v1/consent-receipts/{id}/withdraw`: admin/marketer command returning the existing
  deletion receipt (202); repeated withdrawal returns/retries the same target receipt.

Default tests remain synthetic and free of paid calls. Prove missing/stale/false authorization,
immutable attribution, atomic creation, tenant/role denial, legacy cutover, withdrawal racing media
publication/Check, system expiry revocation, retry/restart and desktop/mobile notice interaction.
Record actual commands/results and limitations in implementation status before claiming verified.

## Implementation decisions

The immutable Python notice registry is the source of version/hash/body truth. PostgreSQL stores
receipts without backfilling old assets; SQLite adds the same table without resetting existing
data. Public notice reads omit session/tenant credentials and current-notice fetches bypass caches.
Receipt timestamps serialize as UTC even when SQLite reloads a timezone-naive value. Withdrawal
reuses the existing deletion outbox rather than adding another queue or independent purge route.
Restricted SQL grants make acknowledgment immutable and revocation irreversible; the system
retention branch may revoke only its exact tombstoned source and records no invented human actor.
