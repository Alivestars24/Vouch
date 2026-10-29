# Architecture decision log

Baseline 2026-10-21. The user authorized the first local implementation slice on this date.
Reversible technical choices recorded as accepted below are implemented only to the stated extent;
consequential business/provider choices remain unresolved. Keep implementation evidence separate
from product or provider claims.

## Accepted implementation decisions

2026-10-22 next-slice acceptance: [authenticated foundation](authenticated-foundation.md) governs
Supabase bearer identity verification, immutable subject mapping, separate non-bypass API/worker
roles, private Storage using user tokens for upload/read, and durable deletion with retry. Local
bootstrap may provision only loopback synthetic accounts and ignored secret configuration. These
choices are now implemented locally; exact passing checks and remaining gates are in the execution
ledger. Hosted rollout and live providers are not part of this acceptance.

2026-10-22 continuation decisions (implemented and verified locally): the existing fixture workflow
now runs on Supabase PostgreSQL in a private `vouch` schema. This avoids
rewriting proven workflow logic to fit the earlier, unused public-schema prototype. The public
prototype migration remains preserved for traceability; direct authenticated writes are removed.
The private runtime schema is migration-owned and has no browser/Data API grants. Fixture identity
remains local-development-only until Supabase JWT and Storage integration is complete.

Review invariants strengthened in this continuation: changing a finding decision invalidates any
prior current approval; deletion erases captions, evidence excerpts and revision drafts as well as
source bytes and fences affected jobs; worker inputs resolve the campaign's exact pinned rule pack.

| ID | Status | Decision and evidence | Revisit when |
| --- | --- | --- | --- |
| ADR-001 | Accepted, locally implemented | Next.js web, FastAPI API/Python worker run with SQLite fixtures or private-schema Supabase Auth/Storage. Runtime credentials are separated. | Hosted deployment, live providers and pilot operations. |
| ADR-002 | Accepted, partially implemented | Claims, leases, fencing, retries, dead-letter, competing worker claims and atomic reservations are verified on Postgres. Remote inbox/outbox/reconciliation remains deferred. | Live side effects. |
| ADR-003 | Accepted and implemented for fixtures | Typed provider ports expose explicit fixture/recorded/live modes; only deterministic fixture mode is callable. | Verified live-provider credentials and authenticated access. |
| ADR-004 | Accepted and verified | API and UI keep analysis lifecycle, machine assessment and human review separate. | Invariant; product/security review required to change. |
| ADR-005 | Accepted and verified for Check | Approval binds manifest, immutable submission version, content/caption hashes and prompt/model versions; reupload supersedes prior review. | Expand to reviewed rulebooks and exports. |
| ADR-006 | Accepted and implemented for capability reporting | Unknown live access is denied; Muse Image is policy-restricted for the India fixture context before upload/call. | Dated provider policy change. |
| ADR-011 | Revised, locally implemented | Verified bearer subjects and current membership control commands over private Postgres tables. API/worker credentials, RLS and direct-mutation denials preserve approval/budget invariants. Fixture identity is separately local-only. | Hosted credential provisioning and operational review. |
| ADR-012 | Accepted, incrementally implemented | FastAPI generates `services/backend/openapi.json`; generated TypeScript checks every outgoing workflow command. Notices/receipt reads have explicit response schemas; other response envelopes remain generic. | Type remaining response envelopes as their boundaries change. |
| ADR-013 | Superseded in part | SQLite remains the zero-setup fallback. The same runtime model also runs with local Supabase Auth/Storage, migration-owned private schema and tested tenant constraints. | Scheduled retention and real media validation. |
| ADR-014 | Accepted | Local API uses port 8010 because port 8000 is occupied on the development machine; override with `VOUCH_API_PORT`. | Deployment/service discovery configuration. |
| ADR-015 | Accepted and verified | Preserve the unused public prototype migration, restrict it to scoped SELECT, and use additive private `vouch` runtime tables generated from the shared domain model. Avoid duplicate repository logic and direct client mutation bypasses. | Consolidate the prototype only with a dedicated migration and retention decision. |
| ADR-016 | Accepted, implemented locally | Supabase bearer tokens are verified against the configured Auth server on each request; immutable subject mapping and current memberships determine access. Separate non-bypass runtime logins, transaction-local context and RLS protect omitted tenant filters. Browser session data is transport, never authority. | Hosted rollout, measured Auth latency or a reviewed cache/revocation policy. |
| ADR-017 | Accepted, implemented locally | Private `vouch-media` objects use generated domain paths. Normal operations forward the caller token; only exact-key cleanup uses a server secret. No client overwrite/delete; incomplete cleanup retains a partial retryable receipt. | Real media normalization, retention scheduling and hosted Storage settings. |
| ADR-018 | Accepted, concurrency-tested | Serialize attachment/revision/deletion per organization with a transaction advisory lock; lock/revalidate assets and lock existing submission revisions. This closes late-derivative deletion races without coupling lineage to worker budget locks. SQLite retains BEGIN IMMEDIATE. | Measured tenant write contention justifies finer-grained locking. |
| ADR-019 | Accepted, implemented locally | Keep `dev` explicitly fixture-only and provide `dev:authenticated` with generated separate env files. Pin `cross-env` for portable Windows/Unix mode selection; use the existing process supervisor. Never put passwords in script arguments/source. | Deployment process management or changed local tooling. |

## Confirmed directions

ADR-030 (2026-10-26, accepted and implemented local visual contract): refine Signal around the
user-supplied creator dashboard's editorial hierarchy without copying its content or inventing its
metrics. Use cool canvas `#F5F7FA`, Vouch red `#930500`, evidence blue `#95BBEA`, dominant white
surfaces and editorial headings across the member workspace, campaign workbench, sign-in and
creator portal. Preserve routes, Auth, tenant/role/notice/version checks, API contracts and human
approval semantics. Workspace summaries may use only returned campaign/action/market data; Find is
now a curated evidence surface, Try exposes only its India policy gate, Track remains deferred, and
decorative creator/product art is not a real result.
This supersedes ADR-024's palette and surface treatment only. Its bounded motion, truthful fixture
provenance and no-hosted-rollout constraints remain in force. See the revised [design
contract](../../design.md).

ADR-031 (2026-10-28, accepted and locally implemented): activate Find only as a tenant-owned curated
evidence collection. Preserve source/permission/verification/capture provenance and distinguish
exact-product proof from category relevance. A campaign-roster mutation must persist the exact
compatible evidence ID, allow an identical replay, and make the evidence link write-once under the
restricted database role. Outreach remains an editable local draft with no send side effect. The
India Try route is a real fail-closed eligibility decision: it blocks before photo input and does
not route around Muse Image policy or silently select another provider. This does not claim broad
social discovery, Wonder assistance, live Try, or Track.

ADR-029 (2026-10-24, accepted implementation contract; invitation/session, initial guest draft
upload/finalize/receipt/version and explicit member-selected feedback publication are implemented
locally and verified through restricted Postgres as of 2026-10-28; later revision and withdrawal
remain deferred): add a true
guest creator capability for one assigned campaign/rostered creator/submission, without creating a
synthetic member or borrowing the issuer's authority. Admins/marketers may issue against a new
empty or existing matching submission; reviewers may issue only against an existing matching
submission. Use at least 256-bit fragment secrets stored only as digests, atomic one-time exchange,
48-hour grants, 30-minute cookie sessions and five-minute upload capabilities. Limit each grant to
five source reservations and 25,000,000 reserved bytes; limit exchange to 10 attempts per 15-minute
client bucket and five attempts per 15-minute token-digest bucket, with attempt records retained no
longer than 24 hours. Add a separate non-BYPASSRLS `vouch_guest` database role/pool and use an
API-only, exact-object-key Storage adapter with its own server credential, never a member token or
the cleanup credential. Grant/session expiry removes access but does not revoke a valid processing
receipt, erase media or reset/extend anchored retention. See the accepted
[creator portal contract](creator-portal.md). Feedback is a separate explicit action bound to the
current version, Check provenance and active authorization; it exposes only the selected snapshot
and is scrubbed with source erasure. The recorded routes and migrations do not imply a later
revision, hosted rollout or live-provider readiness.
Validated content `PUT` replay is accepted only within the active session/grant/capability window
and only for the same server-measured hash and length; it performs no second Storage write or state
regression, while changed bytes conflict. The Supabase guest service holds tenant-lineage and
exact-source database locks through the bounded private Storage write so deletion cannot complete
before a late object appears. Ambiguous failure rolls the database transaction back and the exact
object key is reconciled on retry.

ADR-028 (2026-10-24, accepted implementation contract): extend Signal with scroll-responsive
native 3D and the requested Libraries.dev border beam/activity orbs, after package inspection.
Supersedes ADR-024's three-motion-primitive restriction: keep decorative WebGL on public sign-in;
allow bounded loading effects for actual work elsewhere. Reduced motion and truthful state remain
mandatory. See [contract](oauth-storage-motion.md); verification remains a separate ledger.

ADR-027 (2026-10-24, accepted implementation contract): preserve private immutable originals;
add atomic workspace upload allowances and visible accounting using existing media/cleanup
ownership. Do not ZIP or silently recompress approved media. The 500 MB app allowance is distinct
from Supabase's database and file-storage quotas, and is not a project billing cap. See
[contract](oauth-storage-motion.md). Revisit durable transcoding only with consent/version/time
mapping/deletion ownership and measured savings; do not add another storage service now.

ADR-026 (2026-10-24, accepted implementation contract): add Google PKCE entry through the
existing Supabase browser SDK, fixed same-origin callback and unchanged API subject/membership
authority. Keep the option visibly disabled by default until both Supabase provider state and the
public availability flag are verified. The user reports Google Cloud setup, but the 2026-10-26
local check still reports `external.google=false`. No inferred workspace membership, privileged role or live verification claim follows
from Google identity. See [contract](oauth-storage-motion.md).

ADR-025 (2026-10-23, accepted local configuration): add SHA-pinned GitHub Actions definitions
for the existing default checks and a manual, opt-in ephemeral local Supabase/browser job.
Use locked installs, read-only repository permissions, no hosted secrets, no credential-bearing
traces or artifact uploads, and no deployment. [CI details](../engineering/ci.md) distinguish
local YAML validation from unperformed remote execution. Repository/remote publication and
paid runner use are not authorized by this configuration; revisit after an explicit hosting choice.

ADR-024 (2026-10-23, accepted local implementation contract): redesign the application in place
using the [Signal design system](../../design.md), shared semantic tokens and self-hosted OFL
fonts. Preserve API/state/tenant/consent/review behavior. An original bounded native WebGL brand
sculpture is allowed only on sign-in, with static fallback, reduced motion and user control;
do not load a general 3D runtime, paid gallery assets or processing payloads for decoration.
No hosted rollout, live AI claim or submission eligibility follows from the redesign.

ADR-023 (2026-10-23, accepted and implemented locally; proof in execution ledger): generate compile-time TypeScript wire
types from local FastAPI OpenAPI with a pinned dev-only generator. Verify freshness and use them
for outgoing command payloads while retaining runtime response validation/normalization. Explicitly
schema notices and receipt reads; do not pretend generic dictionary responses are fully typed.
This implements ADR-012 incrementally without replacing fetch or adding a runtime SDK. Revisit
remaining response schemas as each boundary is changed; no database migration is needed.

ADR-022 (2026-10-23, accepted and implemented locally; integrated proof in execution ledger):
require a separate affirmative acknowledgment of a server-owned immutable `campaign_check` notice
at every new upload intent. Store one tenant/uploader/purpose/version/hash receipt per asset and
bind it in new analysis manifests. Do not backfill fabricated acceptance or rewrite historical
hashes; legacy sources become read-only for new work. Withdrawal atomically revokes and reuses the
existing deletion outbox, including durable partial cleanup; system expiry is actorless. This is
local draft processing authorization, not third-party consent, legal review or live Meta permission.
Revisit notice text/version and renewed authorization when verified provider terms or pilot
purposes change. PostgreSQL changes are additive; old receipt provenance must remain immutable.

ADR-021 (2026-10-22, accepted implementation contract): add independent fixture/decoded media
processing through a typed port and a resource-bounded local Docker sandbox. Normalize transiently
and discard output bytes after measuring/hash verification; do not add private derivative keys or
privileged worker reads before their lifecycle/authority is designed. Finalization rechecks current
authorization and source state after external processing. Real decode never implies live evidence.
This deliberately bounds files to 30 seconds/5 MB/1080p/60 fps and zero-origin identity timing;
larger or ambiguous media is rejected. Revisit for durable production processing and reusable
normalized artifacts after measured workload/access requirements.

ADR-020 (2026-10-22, accepted; local implementation, proof in execution ledger): reuse deletion
receipts as the retention outbox, with an independent non-bypass retention login, metadata-only
discovery and scoped scrub-only authority. Nullable actor plus explicit system attribution avoids
impersonation. Lease/fence and three automatic attempts preserve honest incomplete receipts;
authorized manual retry does not extend retention or reset that budget. This avoids another queue
vendor. SQLite upgrades preserve existing receipts transactionally; PostgreSQL history is additive.
Revisit when measured backlog/throughput or additional provider destinations require finer claims.

| ID | Direction | Evidence |
| --- | --- | --- |
| DIR-001 | Documentation before app implementation | User request. |
| DIR-002 | Startup-quality app preserving four-module vision | User request and supplied source. |
| DIR-003 | Useful coverage of most/all supplied model families | User follow-up. |
| DIR-004 | India plus international markets, features gated by eligibility | User answer after provider restriction was identified. |

## Original technical proposals

This baseline is retained for rationale. Accepted/revised decisions above take precedence; this
table does not revert an accepted choice to proposed status.

| ID | Proposal | Rationale and tradeoff | Revisit when |
| --- | --- | --- | --- |
| ADR-001 | Modular Next.js web, FastAPI API/Python worker, Supabase Auth/Postgres/private storage | Fits source and Python media needs; two runtimes increase setup, so keep shared backend package and generated API types. | A tested simpler stack meets the workload better. |
| ADR-002 | Leased Postgres jobs, inbox/outbox and scheduler initially | Fewer services, durable commands and atomic reservations; requires proper leases, fencing and operations. | Queue load/DB contention or managed queue semantics justify migration. |
| ADR-003 | Model capability ports and explicit fixture/recorded/live modes | Work before keys, isolate changing provider formats, show truthful demo state; fixtures still need live contract validation later. | A second provider exposes capability differences. |
| ADR-004 | Independent analysis, assessment and review states | Prevents AI output from becoming legal/human approval. | Never remove this invariant; changes require product/security review. |
| ADR-005 | Immutable input/analysis/rulebook/prompt/model snapshots | Reproducible review and stale-approval prevention; extra metadata/storage lifecycle work. | Retention/export requirements require pseudonymization. |
| ADR-006 | Regional capability policy with unknown eligibility denied | User's mixed-market scope and current Muse Image restriction; requires declarations, enforcement and policy maintenance. | Provider policy changes, with dated evidence and tests. |
| ADR-007 | Standard-mode allowlist, explicit retention/deletion tracking | Real media must not enter training mode by accident; Standard is not ZDR. | A customer requires a verified ZDR-compatible workflow. |
| ADR-008 | Five hosted families, Wonder for bounded evidence dossier | Broad model usage tied to user value; Wonder remains on-demand and cannot mutate business state. | Evaluation shows no incremental value over simpler reasoning. |
| ADR-009 | Check-led implementation sequence, Try gated, Find curated, Track small | End-to-end quality before broad integrations; source has too many MVP features for an unstaffed schedule. | User/team constraints or pilot evidence support another first slice. |
| ADR-010 | No RAG/vector DB or autonomous multiagent product system initially | Pinned rulebooks/evidence fit bounded inputs; simpler auditing and cost control. | Measured context/retrieval quality needs or workflow scale establish a requirement. |
| ADR-011 | Member CRUD via verified user scope/RLS; privileged worker path separately controlled | Avoid service-role bypass for ordinary user requests; worker is still a powerful trust boundary. | Deployment auth/DB client limitations require a reviewed replacement. |
| ADR-012 | First implementation formalizes API from FastAPI/OpenAPI | One generated executable contract reduces TS/Python drift; current prose is the proposed design. | A schema-first generation workflow is adopted explicitly. |

## Unresolved consequential choices

- Official hackathon eligibility, use of pre-event work and third-party models/providers.
- Actual account/region/model entitlements on October 26; five-family coverage is an objective, not a promise.
- Hosting vendor/plans, deployment/processing region, budget and spending authority.
- Permitted alternative Try provider for India; no vendor has been selected or authorized to receive photos.
- Legal owner and reviewed rulebook sources/applicability; no numeric heuristic is approved law.
- Pilot customer, pricing, retention agreement, support commitments and initial product wedge.

## Recording a decision

For each accepted or superseded item, record date, decision owner, evidence, status, affected requirement IDs and migration/rollback implications. Keep provider facts in the dated reference ledger rather than silently updating history. Accepted documents still do not establish that code or operational controls exist.
ADR-030 (2026-10-28, accepted and implemented hosted bootstrap): after explicit user authorization,
apply the complete additive migration chain to `neoapucrxhtwlaqzyikn` without the local fixture
seed, then provision four generated SSL pooler logins that each inherit exactly one NOLOGIN runtime
group. Keep publishable, cleanup and guest Storage keys separated and server-side. Google/Auth
identity never creates tenant authority; an operator binds an exact confirmed subject through an
audited, conflict-refusing onboarding command. Rollback is credential revocation/runtime shutdown,
not a destructive hosted reset; additive schema/data removal requires a separate approved plan.
