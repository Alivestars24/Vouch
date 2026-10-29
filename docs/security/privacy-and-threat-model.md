# Privacy and threat model

Status: security design with a locally tested fixture subset, updated 28 October 2026. Tenant
scope/roles, fixture upload authorization, approval version binding, budget/retry guards, local
deletion tombstones, private Supabase Postgres isolation and direct client mutation denials are
implemented and tested. Changed finding decisions invalidate current approvals; deletion erases
source bytes plus text derivatives and fences worker publication. Real local Supabase Auth,
private Storage cleanup, restricted API/worker credentials and transaction-local RLS are now
implemented. Attachment/deletion serialization prevents late caption derivatives; source locks
permit reviewer/viewer reads but not unauthorized edits. The local creator guest grant, isolated
database pool, one-time exchange, allowlisted submission read, guest-attributed upload/finalize,
immutable authorization receipt and one initial version are implemented and tested. Exact-byte
replay after a lost finalize response is read-only, and the private Storage write remains fenced
against member deletion until the source transaction commits. Explicit allowlisted feedback
publication, later guest revisions, exact-source guest withdrawal and deletion scrubbing are
implemented. Public deployment security remains unimplemented. Production media
isolation and malware scanning also remain unimplemented. Bounded local decoding and
prepared-container erasure are implemented; they are not a production sandbox certification.
Anchored local retention and durable Storage/container retry now have a
separate scrub-only system role; see [retention contract](../architecture/retention-worker.md) and
the command ledger for verification. Both runtime modes refuse staging/
production startup; fixture database URLs must be loopback. This is not a
certification, legal opinion or completed audit. See
[implementation status](../engineering/implementation-status.md).

The local [processing authorization contract](../architecture/processing-authorization.md) adds
separate notice acknowledgment, immutable purpose/version/hash receipts and irreversible
withdrawal through source erasure. Source deletion/expiry also revokes its receipt with truthful
member/system attribution. Missing or revoked receipts block new processing and worker publication;
historical assets are never backfilled. This draft workspace acknowledgment is not depicted-person
consent, universal privacy-rights fulfillment, legal approval or permission for live providers.

Read with [architecture](../architecture/overview.md), [data model](../architecture/data-model.md), [API contracts](../architecture/api-contracts.md), [provider readiness](../integrations/meta-api-readiness.md), and [quality and operations](../engineering/quality-and-operations.md). Current external evidence belongs in [references](../references.md).

## 1. Security outcomes and boundaries

The initial system is a Next.js web app/BFF, FastAPI control API, separate Python media/model worker, and Supabase Auth/Postgres/private Storage. Postgres jobs, inbox, and transactional outbox coordinate work. Logical provider ports are `Reasoner`, `Transcriber`, `Segmenter`, `TryOnProvider`, and `CampaignDossier`, with explicit `fixture`, `recorded`, and `live` invocation modes. `CampaignDossier` shares reasoning transport while enforcing a narrower product contract. A proposed Wonder-backed campaign evidence dossier uses bounded reasoning over authorized campaign facts, not autonomous approval, publishing or outreach.

The main boundaries are browser to authenticated API; creator guest to one submission; API/worker to tenant records and private media; untrusted media to an isolated decoder; authenticated webhook to a durable inbox; worker to model/channel/commerce providers; and machine findings to a human's approval. Every boundary needs an implementation test before pilot use.

Non-negotiable outcomes:

- One organization's users cannot read, modify, export, or infer another organization's records, jobs, assets, spend, or integration credentials.
- An AI result cannot grant access, send unrestricted messages, change rulebooks, approve content, or spend beyond a pre-authorized budget.
- Vouch reports potential issues and evidence coverage. It does not certify legal compliance, establish a person's age from a photograph, or guarantee image fit, identity fidelity, or sales attribution.
- Real customer data cannot silently enter a fixture/recorded demonstration, shared cache, model-training dataset, product analytics event, or developer log.
- Deletion reaches the entire artifact lineage and prevents queued work from recreating deleted personal data.

## 2. Data inventory and proposed retention

All numbers below are proposed pilot defaults, not legal retention obligations or confirmed provider capabilities. Confirm them in customer terms, the privacy notice, and the actual storage/provider configuration before ingesting personal data. Collect only fields needed for the selected module. Hashes and pseudonymous identifiers can remain personal data when linkable.

| Data class | Minimum use and access | Proposed app-managed retention |
| --- | --- | --- |
| Account, membership, tenant configuration | Auth identity and verified organization/brand membership; user and authorized admin | Active account lifetime; deletion workflow after offboarding; any necessary retained record must have a documented reason and expiry |
| Integration tokens and webhook secrets | Encrypted credential store; API/worker by integration scope; never client-readable | Connection lifetime; revoke at disconnect and rotate after exposure |
| Try selfies and generated previews | Consented generation only; scoped worker and shopper delivery; not brand analytics or reviewer browsing | Delete active originals, normalized copies, masks, thumbnails, outputs, and cache copies within 24 hours of initial photo receipt, or earlier on request; retries do not extend the deadline |
| Creator source video, audio, frames, OCR, transcript | Authorized campaign review and evidence; permitted brand users/reviewer/assigned creator guest | Default 30 days after upload; shorter tenant setting allowed; any longer retention requires an explicit agreement |
| Findings and assessment manifests | Evidence review, analysis provenance and scoped report export | Pilot default 90 days; evidence quotes are personal data and follow deletion policy, not an unlimited audit exception |
| Human approvals, consent receipts, essential audit metadata | Proof of action, scope, notice/version and consent purpose; least-privilege reviewer/admin access | Pilot default 90 days; validate with counsel and customer agreement before production |
| Creator contact, campaign roster, orders/attribution | Authorized campaign management and measured outcomes; avoid shipping address, payment data and unnecessary order-line PII | Pilot default 90 days after campaign closure; keep aggregate reporting only after a reviewed de-identification step |
| Webhook inbox and retry payloads | Encrypted minimum payload required to process/deduplicate; operations access restricted | Raw payload default 7 days; deduplication metadata through the documented provider redelivery window, then expire; target window must be verified per provider |
| Operational logs, traces and spend ledger | Opaque IDs, state, timings, error class, counts and monetary units; no raw prompts/media/phone numbers | Logs default 30 days; usage totals/finance records require a separate approved retention policy before paid launch |
| Evaluation fixtures | Synthetic, licensed, or separately consented and de-identified data; engineering/evaluation access | Dataset-specific expiry and withdrawal policy; never automatically retain production inputs |
| Database backups and provider-held copies | Recovery or provider processing; access controlled by vendor and deployment | Finite actual vendor expiry to be recorded before pilot; do not promise immediate physical purge or universal 24-hour deletion |

Try media should live in a dedicated ephemeral bucket excluded from long-lived database/media backups and version history where supported. Backups must not quietly preserve short-lived media. Storage versions, multipart leftovers, CDN copies, temp files, exported reports, webhook bodies, and external model uploads all belong in the deletion inventory. A shopper's downloaded or shared image and WhatsApp/provider-controlled retention are outside Vouch's direct deletion control; explain that boundary.

## 3. Consent, adults, and permitted use

Before requesting a selfie, show the purpose, provider processing, deletion scope, preview limitations, and links to the current privacy notice. Use an explicit affirmative action and adult self-attestation. Store a receipt with purpose, notice version, timestamp, session, and revocation/deletion route. Separate optional marketing consent; using Try must not subscribe someone to marketing.

The pilot is adults-only. Visual models may reject unsuitable/ambiguous imagery as a safety precaution, but cannot verify legal age. Do not store a model's `one_adult_face=true` as proof of adulthood. Block declared minors; offer a non-photo shopping route when age eligibility or permission is uncertain. Do not collect government ID or run facial identity matching to solve this for the pilot. Children/privacy treatment and country-specific notice requirements remain counsel-reviewed launch questions.

Require the uploader to confirm they are the person in the photo or have the necessary permission; the pilot should prefer a person's own selfie and reject multiple-person images. No face recognition, identity inference, sensitive-trait scoring, body reshaping, sexualized generation, or unrestricted prompts. Use server-owned category templates and SKU assets; disable provider search/tools when supported and verify that setting. If that isolation is unavailable, pause the image workflow rather than claim it exists.

Every preview must visibly say "AI preview" and "Fit and size not guaranteed" in the delivered asset/UI. Vouch must not auto-publish a shopper's image. Creator content must come from authorized uploads, official access or a licensed source; public availability alone is not permission to download, redistribute, or train. Rulebooks and regulator names are draft references until current primary sources and counsel confirm jurisdiction and applicability.

### Market eligibility and model privacy

The intended market includes India and international customers. Meta's geographic policy, reviewed for this design on 21 October 2026, lists India as restricted for Muse Image and covers both access location and integrated-product end users. Muse Image Try must therefore be disabled for India; deploying a worker abroad does not resolve an India end-user restriction. Other models/markets require their own current eligibility checks. See the official [geographic use policy](https://dev.meta.ai/legal/geographic-use-policy) and [readiness record](../integrations/meta-api-readiness.md).

Enforce an explicit model-by-market policy on the server before reservation, enqueue, provider invocation and result delivery. Bind the policy version and evaluated operator/account, deployment and end-user eligibility facts to each live attempt. Use current trusted account/integration information and explicit user country declaration where needed; IP location is a supporting signal, not proof of residency, citizenship or permission. Do not infer country from a face, silently accept client flags, collect precise location unnecessarily, or offer VPN/foreign-hosting workarounds. Unknown/conflicting eligibility fails closed for that model. Keep eligible Find/Check/Track functionality available. An alternative image provider is a separate reviewed integration with suitable market rights, retention terms, consent, pricing and explicit product labeling; never silently fall back.

Meta Standard mode's documented no-training setting is distinct from zero data retention. Request `store:false` where the supported response API allows it and record the actual configuration; this does not eliminate all provider retention. Meta's [file-handling documentation](https://dev.meta.ai/docs/file-handling) states files do not expire by default and supports explicit expiration and deletion. Track every remote file ID, set an expiry compatible with the anchored app deadline, explicitly delete after use, and reconcile failures; never reset the user's deletion deadline when creating a derivative or retry upload. One bounded synthetic Spark response has been live-tested with `store:false`; uploaded-file retention/deletion and product-media behavior remain untested.

The documented [zero data retention policy](https://dev.meta.ai/help/policies-and-privacy/zero-data-retention) requires account enablement and has feature/model restrictions, including uploaded Files API workflows. The current upload-based architecture must not be called ZDR. If a customer requires ZDR, first design and validate an eligible inline/no-state path under the actual approved account, or decline that processing. Confirm retention/training settings for every provider, including a replacement Try provider, before using real shopper or creator data.

## 4. Tenant authorization and roles

Authorization is server-side and repeated for every action and resource lookup. Resolve the authenticated user and current membership from trusted claims/database records; never accept an arbitrary client `organization_id` or `brand_id` as authority. Every tenant-owned row, object path, job, cache key, event, export and provider connection is scoped to its organization and, where applicable, brand. Initial member permissions are organization-wide; storing `brand_id` prevents mixed parentage but is not a promise of brand-restricted roles. An agency needing private teams for each brand must use separate organizations until explicit brand-level permissions are implemented and tested. Agency access to organization A does not grant access to organization B.

| Principal | Allowed scope | Explicit restriction |
| --- | --- | --- |
| Admin | Membership/integration/settings management and authorized organization work | Admin membership alone does not create a reviewer sign-off; require an assigned Reviewer permission for approval |
| Marketer | Campaigns, authorized content submission, findings and fix requests | Cannot grant roles, activate rulebooks, sign off as a reviewer, or browse shopper selfies |
| Reviewer | Assigned checks, evidence, finding dispositions and sign-off | Cannot approve stale/incomplete assessments or access unrelated tenants; reviewer authority must be current at action time |
| Viewer | Authorized read-only campaign/report views | No mutation, private shopper-media browsing, or arbitrary exports |
| Creator guest | One grant's campaign/submission and permitted fix discussion | No roster, other creators, shopper data, orders, team directory or tenant-wide API access |
| Worker/service | Narrow job/integration operations for the job's tenant | Cannot derive tenant authority from untrusted webhook/model content; elevated database credentials remain server-only |

Enable RLS for application tables and private storage policies; test both allowed and denied paths with two organizations and multiple brands. Use composite tenant foreign keys/constraints where practical to prevent a child in tenant A referencing a parent in B. An object path prefix alone is not authorization. Worker/service-role credentials may bypass RLS: require explicit scoped queries, trusted job context, and application-level authorization tests even with RLS present. Default deny new tables/buckets until reviewed.

Require recent authentication for role changes, credential connections and sensitive exports. Use secure, HttpOnly, same-site session cookies where applicable; validate issuer/audience/expiry/signature on API tokens and reject revoked/expired membership. Protect cookie-authenticated mutations against CSRF, enforce an origin allowlist/CORS policy, and avoid credential-bearing query strings. Require MFA for production operator accounts where supported. Staff access is exceptional, time-bound, justified, and audited.

### Creator guest grants

Generate a cryptographically random token with at least 256 bits of entropy; store only its SHA-256
digest, grant scope, expiry, remaining reservations and revocation state. The invitation TTL is 48
hours. Exchange once for a 30-minute scoped guest session; burn exchange capability atomically and
reissue after expiry/revocation. Admins/marketers may issue for a new empty or existing matching
submission; reviewers may issue only for an existing matching submission. Grant permission to work
on one assigned submission, not a full user JWT or borrowed member principal. Revalidate scope before
each upload, reupload and read through a separate non-BYPASSRLS `vouch_guest` database role/pool.

Limit each grant to five atomically reserved sources and 25,000,000 reserved bytes, with upload
authority lasting no more than five minutes. Limit exchange to 10 attempts per 15-minute
privacy-minimized client bucket and five attempts per 15-minute token-digest bucket; retain attempt
records no longer than 24 hours and keep denial responses uniform. Guest Storage access is
API-proxied, exact-object-key access using a separate server-only credential. Never expose that
credential, substitute a member token, or widen the cleanup credential. Treat it as RLS-bypassing
authority and prove application scope with adversarial tests.

Grant/session expiry removes access; it does not revoke a valid processing receipt, erase an accepted
source, release bytes whose cleanup is unconfirmed or reset/extend anchored retention. Consent
withdrawal and erasure are separate explicit, source-scoped operations with durable cleanup.

Avoid tokens in analytics, logs and referrer headers. Use a URL fragment or a minimal exchange page that immediately removes the token from browser history, `Referrer-Policy: no-referrer`, and no third-party tracking there. Treat an emailed link as a bearer credential; it proves link possession, not legal identity. Approval remains restricted to an authenticated assigned reviewer.

## 5. Uploads, webhooks, and untrusted media

Signed upload intents bind tenant, submission, generated object key, maximum bytes, permitted type and expiry (proposed five minutes). The server chooses the object name. Completion re-checks ownership, actual bytes/magic type, checksum, allowed codec and duration; client MIME declarations and extensions are untrusted. Keep uploads quarantined until validation completes; never serve active HTML/SVG/script under an application origin. Sensitive downloads use a scoped authorization check and short-lived signed URLs (proposed one minute), private buckets, `Cache-Control: no-store`, and no public CDN caching. Deleting an object and denying new URLs cannot retract a recipient's saved copy.

Verify each webhook using the provider's documented signature over the original raw request bytes, correct installation secret, and any documented timestamp/replay checks. A webhook verification challenge token alone does not authenticate POST events. Resolve tenant from the verified installation mapping. Reject invalid signatures without processing. Bound body size and sanitize error responses.

Before acknowledging a valid delivery with 2xx, atomically insert a durable inbox receipt and corresponding outbox/job intent. Uniqueness must cover provider, integration/installation and stable event ID; a duplicate ID with a conflicting body digest requires rejection/investigation, not silently replacing the first receipt. Already-durable identical duplicates can return success without redoing side effects. If durable persistence fails, return a retryable non-success response. Validate entity versions and handle out-of-order events; signature-valid events are not automatically current. Store the minimum encrypted payload needed for retry and delete it under the inbox retention policy.

Prefer direct upload for the pilot; disable arbitrary remote URL ingestion. When an official connector needs remote media: fetch only authorized, allowlisted HTTPS provider hosts, revalidate every redirect and DNS resolution, block private/link-local/loopback/metadata IP ranges including IPv6 and alternate encodings, and enforce network egress restrictions. Set byte/time/redirect limits; never forward application credentials to user-supplied destinations.

Run ffmpeg/image decoding in a restricted worker process/container with no application secrets, a read-only base filesystem, per-job scratch directory, no arbitrary outbound network, CPU/memory/disk/process/time limits and patched pinned dependencies. The API supplies files and receives validated outputs; it does not execute file-provided commands. Never interpolate filenames into shell commands. Strip image EXIF/GPS, verify outputs, clean scratch on success/error/cancellation, and run a sweeper after crashes. Quarantine parser failures instead of repeatedly retrying malformed media.

## 6. Models, evidence, and approval integrity

Treat captions, OCR, transcripts, websites, attachments and provider output as untrusted data. They cannot override system instructions, call privileged tools, select another tenant's files, activate a rulebook, or send messages. Enforce schema/length/enum/range validation, known rule IDs and evidence-source IDs outside the model. Escape rendered output and parameterize database queries. Model text is a suggestion, never executable code or an automatically accepted factual/legal claim.

A Wonder evidence dossier must cite authorized existing finding/source IDs, identify missing evidence and stop at a configured token/cost/time budget. No direct arbitrary URL fetch, code execution, unrestricted web tools or cross-tenant retrieval. External grounding, if later added, is a separately reviewed capability with source provenance and injection defenses. Dossier conclusions cannot set `review_status`, activate a rulepack, change financial attribution, or trigger messages. The same eligibility, privacy, retention and audit controls apply to it as to shorter reasoning calls.

Every analysis pins an immutable input manifest: original and normalized asset hashes, exact caption hash, rulepack version/content hash, prompt and schema versions/hashes, provider/model identifier and observed version if available, preprocessing/sampling configuration, and source/timestamp lineage. Unknown provider revision is recorded as unknown; do not imply full reproducibility. Cache keys include tenant, all relevant versions, preprocessing, and content hashes; no cross-tenant reuse of personal media.

Keep these separate:

- `analysis_status`: `queued`, `running`, `completed`, `partial`, `failed`, `cancelled`.
- `machine_assessment`: `no_issues_detected`, `fixes_suggested`, `potentially_blocking`, `human_review_required`, `not_assessed`.
- `review_status`: `unreviewed`, `changes_requested`, `approved`, `rejected`, `superseded`, `revoked`.

`no_issues_detected` means no issue was found within declared evidence coverage, not "compliant." Missing transcript, unsupported language, failed frame decoding, unverified timestamps, low-quality evidence or unavailable required provider yields partial/not-assessed/human-review states. Missing evidence is never a pass. Model confidence is an uncalibrated ranking signal until evaluated, not a probability of legality or correctness.

Approval is an authenticated, permission-checked human action binding the exact input/analysis manifest, finding dispositions, reviewer, timestamp and optional reason. A content/caption edit or required reanalysis creates a new revision; prior sign-off is retained as history and marked superseded/stale for current workflow. A rulepack effective-version change creates a re-review obligation rather than retroactively changing what was approved. Use optimistic version checks or row locks to reject an approval racing with a reupload or reanalysis. Partial evidence and unresolved findings cannot receive routine approval; the pilot has no silent override path. Reviewer feedback enters an explicitly curated evaluation workflow, not automatic model training.

## 7. Audit trail and deletion

Audit permission changes, grant issue/revocation, content submission, analysis versions, reviewer decisions, export, integration access, deletion and privileged operator access. Keep opaque resource IDs, actor role, time, action, result and minimal provenance. Do not embed raw media, phone numbers, credentials, full prompts/transcripts or unnecessary claim quotes in the event stream.

Proposed tamper evidence: append-only application writes, tightly restricted database roles, chained canonical event hashes per organization, and periodic signed checkpoints stored separately. A hash chain detects some modification only when a trusted checkpoint survives; a database administrator with all keys/checkpoints may still rewrite history. This is not a legally certified ledger or protection from every privileged attacker. Do not add a blockchain or indefinite WORM retention to the pilot. Retention-limited audit partitions, privacy-safe metadata and separately stored deletable evidence must support the agreed deletion policy; hashes are not automatic anonymization.

Deletion is a resumable, idempotent workflow: authorize the requester; freeze new work and revoke guest/media access; mark a deletion tombstone; cancel/stop queued jobs; traverse the artifact lineage; delete active objects/versions, rows requiring erasure, cache/temp/exports and provider files where an endpoint exists; record per-destination outcomes; retry failures; issue a scoped receipt with remaining limitations. Running workers condition every publish/write/delivery intent atomically on the current resource version and absence of a tombstone; an earlier read-only check is insufficient. An already in-flight provider call may still finish: record any returned artifact solely for cleanup, retain unknown outcome in the receipt, and never deliver it after cancellation/deletion. A restore must replay deletion tombstones before serving traffic so a backup cannot resurrect deleted data.

Creator-visible feedback is an explicit, allowlisted snapshot rather than an automatic projection of
internal findings or reviewer rationale. It preserves exact Check provenance and version labeling.
Member deletion and retention erasure scrub its message and timestamp range under narrow database
column grants while retaining only the identifiers and provenance needed for lineage/audit history.

A receipt distinguishes request accepted, active Vouch copies deleted, provider request acknowledged, provider deletion confirmed where supported, and finite backup expiry. Do not label a provider copy deleted solely because Vouch dropped its file ID. Document irretrievable channel recipients/shared copies and any narrowly justified retention exceptions. If actual provider retention cannot meet the intended notice or consent terms, use synthetic data until the product owner resolves the policy and terms.

## 8. Threat register and evidence needed

These are design risks, not confirmed vulnerabilities in an implementation.

| Lower-trust input/principal | Boundary and harm | Required control and planned proof |
| --- | --- | --- |
| User in tenant A changes a resource ID | Cross-tenant media/findings/order disclosure | Server checks + RLS/storage policies + tenant foreign keys; two-tenant allow/deny integration tests |
| Forwarded/replayed creator link | Unauthorized upload or exposure of another creator's content | Scoped expiring hashed grants, atomic exchange, revocation; token replay/scope tests |
| Forged/replayed provider event | Fake orders, duplicate generation, unauthorized messages/spend | Raw-body signature, installation mapping, inbox unique key/outbox transaction; duplicate/reorder/concurrent delivery tests |
| Malformed file or arbitrary media URL | Decoder escape, resource exhaustion, SSRF, internal credential access | Quarantine, process/resource/network isolation and strict connector allowlist; bounded synthetic parser/URL tests |
| Text in video tells model to ignore rules | Prompt injection causes fabricated evidence or privileged action | Untrusted-data separation, no privileged model tools, output schema/source validation; adversarial labeled fixtures |
| API retries and many concurrent shoppers | Double billing, spend cap bypass, abusive generation | Rate limits, reservation ledger and idempotent provider attempt IDs; concurrent budget/timeout tests |
| Insider or leaked elevated credential | Broad tenant access or audit rewriting | Least privilege, encryption, secret rotation, staff-access audit and independent checkpoints; access review and restore drill |
| Reupload/pack update during sign-off | Old evidence appears approved for new content | Immutable revisions and atomic version comparison; approval/reupload race tests |
| Retention sweeper misses derivatives/provider copies | Broken deletion promise and selfie exposure | Artifact inventory, tombstones, per-copy receipt, backup re-delete; deletion and restore tests |
| Broken quality/safety classifier | Unsafe or misleading output sent to shopper | Explicit consent, fixed templates, quality coverage, conservative fallback and human review; cohort/adversarial evaluation |
| Shared recorded demo result | Another person's image is leaked or shown as live | Tenant-scoped consented fixture IDs and visible recorded-mode label; no personal-image substitution across sessions |

## 9. Pilot release decisions

Before real users: assign a security/privacy owner; approve the data inventory, notice and deletion semantics; verify model/provider retention and training settings in the actual account; enable isolation controls; pass authorization/webhook/upload/deletion tests; rehearse incident and backup recovery; and validate the applicable rulebook wording with counsel. Secrets must be environment-managed, server-only, redacted and rotatable. Disable sensitive request/response capture and session-replay recording on upload, creator and shopper flows.

Do not claim SOC 2, GDPR/DPDP compliance, guaranteed age detection, guaranteed no-training, legal approval, or universal 24-hour erasure based on this design. Record the primary-source and counsel review needed for each market in the references/readiness ledger. The initial launch gate is a small consenting pilot with documented limitations and a working support/deletion contact, not an enterprise compliance badge.
