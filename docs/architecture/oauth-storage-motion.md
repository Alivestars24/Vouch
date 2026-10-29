# Google entry, private storage allowance and motion

Date: 2026-10-24. Accepted implementation contract (ADRs 026–028); execution and
verification are recorded separately in [implementation status](../engineering/implementation-status.md).
This extends the [authenticated foundation](authenticated-foundation.md), not its tenant,
processing-authorization, version or cleanup boundaries.

## Google entry

Keep password sign-in. Add a Google option through the existing Supabase browser SDK with
PKCE, a fixed same-origin `/auth/callback`, and no caller-selected return destination.
Disable automatic URL session detection; the callback explicitly exchanges the code, removes
query/fragment credentials from browser history, and navigates to `/`. Callback failures show
safe text and clear local private state. Do not log or display provider payloads.

Google proves identity, not workspace authority. The API still verifies the bearer subject,
requires its immutable domain-user mapping, and checks current memberships. Never assign an
organization or admin role from email, a Google profile or user-editable metadata. An account
without access receives an honest access message, not an endless sign-in loop.

The user now reports completing Google Cloud-side setup, but the 2026-10-26 application check still
finds local Supabase Auth reporting `external.google=false`, no runtime public enable flag and a
disabled button. `NEXT_PUBLIC_GOOGLE_OAUTH_ENABLED=true` is a
public availability flag, not a credential or authorization control. Enabling it requires the
provider configuration and exact redirect allowlist first. No client secret enters Next.js
public variables. Local SDK/callback tests and Google Cloud configuration alone do not establish
real Google login success.

## Private storage and space

Supabase's published Free plan currently distinguishes **500 MB database** from **1 GB file
storage** ([pricing](https://supabase.com/pricing), checked 2026-10-24). These are provider plan
figures, not measured remaining capacity or an entitlement verified for this account.

Authenticated uploads already use the private `vouch-media` bucket, one immutable original per
asset, and no duplicate relational blob. Preserve caller-token reads/writes, generated keys,
5,000,000-byte individual limits, current membership checks and confirmed exact-key deletion.
The fixture backend retains its explicitly synthetic database-byte mode.

Add a conservative **500,000,000-byte application allowance per workspace**, independent of
provider billing. Atomically admit/reserve upload intentions before bytes are accepted. Count
reserved, retained and unresolved cleanup bytes; neither a failed upload response nor a
tombstone proves a remote object is absent. Release retained capacity only after the existing
cleanup path confirms erasure. Expired never-uploaded reservations may be released only when
they cannot still write. Concurrent uploads cannot each spend the same remaining allowance.
Existing data is preserved; an over-limit workspace can read/delete but cannot add new uploads.

Expose a tenant-scoped typed usage read and a readable storage meter with loading, failure and
retry states. Unknown usage is not zero. The meter is Vouch's workspace accounting, not the
Supabase project/organization billing dashboard: other workspaces and buckets also consume
provider capacity. Production provisioning must allocate all workspace allowances within a
verified project budget and monitor actual provider usage; this is not a global billing cap.

Do not ZIP originals or silently re-encode reviewed media. MP4/WebM already contain compressed
media, ZIP adds no useful playback contract, and lossy changes would invalidate exact-byte
hashes and approvals. Keep the existing transient decoder output ephemeral. Creators may export
a smaller draft before upload; it becomes the new reviewed original. In-app transcoding or
cross-asset deduplication is deferred until it has explicit consent, source-time mapping,
reference ownership and deletion accounting. No storage-saving percentage is claimed.

## Requested motion, with truthful state

Extend Signal's original ribbon with scroll-responsive 3D rotation, without scrolling control
or content movement. Keep bounded rendering, user pause, offscreen/document suspension,
resource disposal and static reduced-motion/failure fallbacks.

Use the specifically requested Libraries.dev border beam and thinking orb packages after
checking their licenses and implementation. One subtle beam belongs to the public sculpture;
orbs accompany actual loading or queued/running work with an accurate text label. They never
indicate model reasoning, progress percentage or success without server evidence. Terminal and
unknown states do not display an ongoing-work animation. No media or account data enters
graphics code. ThreeUI remains visual inspiration; no unlicensed gallery assets are copied.

## Acceptance

- Password login still works; Google disabled state, start/failure, PKCE callback, URL removal
  and fixed redirect are tested without contacting Google.
- Storage accounting is scoped and concurrency-safe; pending cleanup does not release space;
  retries, expiry and deletion retain their existing invariants. Usage errors never become zero.
- Loading effects follow real state; reduced motion, hidden/offscreen suspension, cleanup and
  scroll response are tested. Inspect desktop/mobile layout and keyboard operation in a browser.
- Update generated contracts and affected requirements/design docs. Keep live-provider access,
  hosted rollout and hackathon eligibility separate from local implementation evidence.
