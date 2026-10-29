# Architecture

Status: implemented local fixture architecture, updated 2026-10-28. The Next.js web, FastAPI API and
Python worker run against SQLite or local Supabase PostgreSQL through one domain model. Local
Supabase Auth, private Storage and restricted runtime credentials are implemented. Read
[implementation status](../engineering/implementation-status.md), [decisions](decisions.md) and
[Meta readiness](../integrations/meta-api-readiness.md) with this document.

### Implementation truth

The [authenticated foundation](authenticated-foundation.md), written before implementation, defines
Supabase sign-in, restricted server roles, transaction scope, private Storage and deletion retry.
The execution ledger separates real local Auth/Storage proof from deterministic provider results.
The [2026-10-24 extension](oauth-storage-motion.md) keeps this architecture while adding disabled-by-default
Google PKCE entry, derived workspace storage allowances, and bounded UI motion. No extra storage,
queue or 3D framework is introduced. Google remains disabled in the checked local Supabase/provider
state even though the user reports completing the Google Cloud-side setup.
The [retention process](retention-worker.md) adds actorless expiry cleanup and bounded durable
Storage retries under a third non-bypass credential; verification is recorded per check.
The [processing authorization boundary](processing-authorization.md) now adds immutable,
purpose-bound notice receipts at intake, legacy read-only cutover, and withdrawal through that
same deletion outbox. Rights attestation, processing authorization and human approval are distinct.
Receipt loss/revocation also cancels queued work and blocks late publication. Live provider
activation requires its own reviewed notice/terms; the local draft never grants that permission.

The SQLAlchemy domain implementation now persists to Supabase Postgres in the private `vouch`
schema. An additive migration owns this runtime schema; the original public-schema prototype is
preserved and allows only tenant-scoped reads from authenticated Data API clients. All runtime
mutations pass the API or worker. Authenticated mode uses separate non-bypass API/worker/guest logins,
transaction-local scope and private membership/guest-capability helpers; the owner is bootstrap/migration-only.
The preserved fixture path uses local owner persistence and synthetic headers. Both modes refuse
non-development/test environments; hosted application rollout remains gated.

| Boundary | Implemented now | Verified now | Still proposed |
| --- | --- | --- | --- |
| Next.js web | Sign-in/session recovery, workspace selection, curated Find, India fail-closed Try decision, campaign/upload/Check/review/revision/approval, deletion receipts and scoped creator portal with one initial upload/draft path | Component tests and production build; desktop/mobile real local Auth and guest read proof; focused component proof for Find, Try and initial guest mutation | Self-service onboarding/recovery, full guest mutation browser journey, feedback/later revision/withdrawal and Track |
| FastAPI API | Server-verified identity, private media, bounded optional decoded validation, immutable provenance, command guards, evidence-bound Find roster mutation and scoped guest invitation/recovery/exchange/read/revoke/upload/finalize/receipt/initial-version commands | Mock failures, real local Auth/Storage/guest pool, restricted Find/guest integration, synthetic media decoding and cancellation | Guest feedback/later revision/withdrawal, hosted deployment, malware scan and production isolation |
| Python processes | Check claims/leases, output validation and publication; separate anchored retention and durable Storage cleanup | Concurrent claims, spend cap, deletion fencing, system audit attribution and bounded cleanup retries | Live provider reconciliation and operational SLOs |
| Supabase | Private runtime, composite tenant keys, separate API/Check/retention/guest roles, Auth subjects, private media bucket and server-only exact-key guest Storage proxy credential | SQL role/policy proofs, restricted-login and initial guest-mutation integration, schema parity and advisors; counts in execution ledger | Hosted bootstrap and operational gates |
| Provider ports | `Reasoner`, `Transcriber`, `Segmenter`, `TryOnProvider`, `CampaignDossier` typed interfaces; first three deterministic fixtures plus server-only catalog and bounded Spark smoke adapters | Fixture contract outputs/failures, account catalog and one synthetic `store:false` Spark structured response | Product live adapters, file/media flows and Voice Transcribe/SAM/Wonder execution |

This status includes one bounded synthetic Spark live call and an account-catalog probe. It does not
imply a live product Check/provider call, media upload, deployment, legal review or hackathon
eligibility.

## 1. Shape and boundaries

Use a modular application with separate web, API and worker processes, one relational system of record and private media storage. These are deployment/runtime boundaries, not independently owned microservices. They share versioned contracts and ship together initially.

| Component | Proposed responsibility | Boundary |
| --- | --- | --- |
| Next.js web | Brand workspace, creator guest portal, mobile Try, reviewer timeline | No model/provider keys or privileged data role in the browser. |
| FastAPI API | Authentication/authorization, commands, signed upload requests, jobs, webhook inbox | Validates tenant/role and durable input before work is accepted. |
| Python worker | Media normalization, model stages, rule execution, cleanup, outbox delivery | Long tasks in a container with ffmpeg; never in a short web request. |
| Supabase Auth/Postgres/private storage | Identity, relational records, row policies, private artifacts | User authorization and worker service authorization are distinct. |
| Provider adapters | Model, messaging, commerce and discovery transport | Normalize provider differences; application does not depend on SDK payloads. |
| Scheduler | Leases/retries, retention scans, reconciliation | Runs independent of an individual job or web process. |

Container host, paid plans and deployment regions remain open decisions. Local lockfiles currently
pin Next.js 16.4.2/React 19.3.1, Supabase CLI 2.121.0, and the Python environment resolved from the
backend lockfile. These local versions are implementation evidence, not a production hosting
decision.

An editable [system diagram](vouch-system.drawio) accompanies this document. Data storage is shared by API and worker; it is not a step after inference.

## 2. Domain modules

**Workspace:** organizations, membership, brand, permissions, integration credentials, capabilities and usage.

**Campaign:** product snapshots, creator roster, source submissions, rulebook selection and goals. Campaign context is shared; modules can be independently entitled.

**Check:** versioned media/caption submission, evidence extraction, rule assessment, human review, revisions and audit history.

**Try:** region/capability eligibility, consent, product choice, photo suitability, composition, quality gate, delivery and deletion.

**Find:** authorized candidate metadata, curated/provided evidence, later official/licensed discovery. A visual concept match is not proof of an exact SKU or endorsement.

**Track:** append-only observed events, links/codes, verified order webhooks, deterministic attribution and refunds.

**Campaign dossier:** on-demand Wonder summary of a bounded authorized evidence snapshot; cite source IDs, show gaps, suggest next steps for a human.

Keep these modules within one application package initially. Extract a service only when load, ownership or policy isolation provides a concrete reason.

## 3. Meaningful model coverage

| Hosted family | Planned job | Required proof |
| --- | --- | --- |
| Muse Spark | Visual facts and rule-grounded judgments | Schema validity, evidence precision/recall, uncertainty and timestamps. |
| Muse Voice Transcribe | Speaker turns and multilingual speech | Transcript quality, chunk offsets and turn-level timing. |
| SAM 3.1 | Product masks/tracks and measured visual exposure | Mask quality, source time mapping and sampled-coverage limits. |
| Muse Image | Controlled eyewear preview in eligible markets | Policy, consent, fidelity and identity-preservation evaluation. |
| Muse Wonder | Cross-record campaign evidence dossier | Valid record citations, grounded recommendations, latency and spend cap. |

Public catalog and regional evidence are maintained in [readiness](../integrations/meta-api-readiness.md); runtime availability is not inferred from this table. Image remains restricted from/for India under current policy. Open-weight Spark Open/Glimmer are later benchmark options; Wonder Full/Muse Code are development-tool variants, not additional product API coverage.

Use a separate logical `CampaignDossier` contract implemented through the shared reasoning transport. It is not an autonomous agent with approval, messaging, payments, shell, unrestricted browsing or rule-publication authority.

## 4. Request and worker flow

1. Authenticate, resolve membership/guest capability, validate tenant resource ownership and capability eligibility.
2. Validate and finalize media in quarantine; compute source hashes from verified bytes. No arbitrary URL fetching in the first slice.
3. A transaction writes the immutable command/input snapshot, job, idempotency record and conservative budget reservation.
4. Return an accepted operation ID; UI polls status with backoff. Cancellation is a command, not deletion of history.
5. Worker leases the job, increments a fencing token, commits, and performs stages outside the database transaction. Persist stage outputs and remote IDs so recovery can resume safely.
6. Validate typed model output and evidence invariants before a result is published. Persist usage, audit and any outbound action in the same completion transaction.
7. Separate outbox delivery sends approved messages/notifications; separate cleanup removes expired local and remote artifacts. API/webhook acknowledgement does not wait for model execution.

The first slice implements the job table, leases, fencing, retry scheduling and dead-letter states
through SQLAlchemy on both databases. SQLite serializes transactions with `BEGIN IMMEDIATE`;
Postgres claims use `FOR UPDATE SKIP LOCKED`. Tests prove competing workers claim one job once and
competing reservations stay within one authorized budget. Remote paid outcome reconciliation is
still deferred because fixture providers have no paid side effects.
[PostgreSQL locking documentation](https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE)

## 5. Check pipeline

Normalize source media in an isolated process; preserve original-to-derived timestamps and dimensions. Extract audio, visual facts and concept tracks in parallel only within per-provider and per-tenant limits. Transcription chunking obeys both duration and request-body size; SAM sampling is task-specific, not universal.

Evidence is typed: speech turn, visual observation, OCR/caption span, track coverage and missing interval. A zero match on sampled frames is not proof of absence between frames. Keep uncertain facts and unknown intervals.

Run deterministic predicates only on sufficient evidence. Run judgment rules with a pinned rulebook and schema; validate returned rule IDs, citations, time ranges and limitations. Draft policy heuristics do not become law through a prompt.

Publish assessment separately from lifecycle and human review. A partial required stage cannot produce `no_issues_detected`. An approved revision must be unchanged and all required gates resolved. Updating prompts, models or rulebooks creates a new analysis; it never rewrites the old approval.

## 6. Try pipeline and eligibility

Evaluate capability status **before** selfie intake/provider upload. Store operator/access, deployment/processing and end-user region facts independently with their provenance and the policy version. Unknown required eligibility fails closed. Region selection in the UI or server location alone cannot prove eligibility.

For an eligible provider: explain purpose/vendor/retention; obtain explicit consent and adult attestation; validate product; accept private photo; strip metadata; run suitability/safety checks; generate using fixed prompts; check output for product fidelity/artifacts; apply AI-preview label; deliver privately; schedule deletion against the original anchored deadline. No face identification or guaranteed age/size inference.

A narrowly scoped conversation can run on the first-party web surface before WhatsApp approval. The product must name the actual channel/provider/mode. A policy block must not silently trigger another image vendor; any permitted alternative requires its own evaluation, privacy disclosure and access check.

## 7. Data access and credentials

Local identity is either explicit fixture headers or a server-verified Supabase bearer token,
resolved against current active membership. These are separate development/test modes, never an
authentication fallback. Domain mutations remain API commands so
approval, upload, budget and deletion rules cannot be bypassed through direct Data API writes.

Authenticated local operations use separate least-privilege API, Check-worker and retention
credentials with transaction-local scope. The private runtime schema denies `anon`/`authenticated`
access and enables RLS. Database-owner persistence remains only in the explicitly synthetic fixture
mode. Hosted credential/bootstrap, backup and operational readiness remain release gates.

The API and worker share the domain implementation. No second frontend authorization policy, duplicated business logic in server actions, or provider SDK calls scattered through UI components.

## 8. Integration reliability and honest metrics

Verify webhook raw-body signatures with the correct tenant integration secret, then insert an inbox item under a unique provider-event key before acknowledgement. Reject conflicting replay bodies; duplicate deliveries do not create duplicate orders/jobs. Long work begins after durable receipt.

Write pending external actions to an outbox in the domain transaction. An outbox prevents lost intent; it does not guarantee exactly-once remote delivery. Track delivery IDs, retries, timeouts and uncertain outcomes.

Store the reason for attribution: verified discount code, stored checkout tracking identifier, or unmatched/conflicting evidence. Do not reconstruct missing order identity from a guessed UTM. Separate demo data and test orders from live revenue; handle refunds with ledger adjustments.

## 9. Cost, privacy and observability

Budget checks are atomic reservations plus actual usage settlement, per organization and shared provider team. Estimate maximum bounded stage costs including allowed retries. Provider failures with unknown billing leave a reconciliation state; spend is not erased by worker cancellation.

Cache only authorized deterministic/expensive derived work within the tenant and retention window, keyed by media/caption hash, prompt/schema/rulebook/model version and relevant policy. A cache hit cannot bypass consent, new policies or missing retained source evidence.

Telemetry includes operation/stage IDs, provider request IDs, latency, usage units, status and redacted errors. Media, transcripts, tokens and signed URLs are excluded. Evaluation payloads require separate consent and access controls.

Application deletion includes source, derived files, previews, chunks, temp disk, cached copies, exports and remote files. Provider retention limits and backups are distinct disclosures, not a promise of instant universal erasure.

## 10. Repository layout

The current first-slice inventory is:

```text
apps/web/                     implemented workspace, Find, Try policy gate, Check and creator guest surfaces
services/backend/
  src/vouch_backend/          API, domain service, worker, providers and models
  tests/
  openapi.json                generated executable HTTP contract
supabase/migrations/          canonical PostgreSQL schema and RLS policies
supabase/tests/               pgTAP tenant-policy tests
docs/                         canonical product/engineering reference
```

API and worker are separate entrypoints from the same Python package. The intentionally flat
backend module is a first-slice decision; split domain packages only when the second slice creates a
real ownership or reuse boundary.

See [data model](data-model.md), [API contracts](api-contracts.md), [quality and operations](../engineering/quality-and-operations.md) and [roadmap](../engineering/roadmap.md) for the build gates.
