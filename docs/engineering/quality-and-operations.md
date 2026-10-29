# Quality, evaluation, and operations

Status: engineering contract with a verified local fixture subset, 28 October 2026. The same API/
worker suite passes on SQLite and Supabase Postgres; real local Auth/private Storage, separate
restricted logins and SQL policy/isolation assertions pass (current counts are in the ledger).
Anchored retention restart, leases,
fences, exhausted retry and real Storage cleanup pass locally. Browser tests cover desktop/mobile
and sign-in widths 320/768/1024/1440 with keyboard focus order. There is no deployment, measured SLO, live model
evaluation or production recovery evidence. Targets below remain proposed unless
[implementation status](implementation-status.md) records a passing check.

The bounded creator guest initial-draft path is locally verified through separate-role SQL assertions,
authenticated integration tests and desktop/mobile browser interaction. Coverage includes fragment
scrubbing, one-time exchange/replay denial, cookie resume, current issuer authority and allowlisted
submission reads. Guest upload/content/finalize, applicable notice/receipt attribution and initial
version publication have backend/component proof. Explicit allowlisted feedback publication has
service, SQL, restricted-runtime and component proof; later revision and withdrawal remain absent.
Member recovery/renewal, simultaneous two-connection exchange and
bounded blocked-bucket writes are verified locally. The deployment-specific trusted-proxy/client-
bucket contract remains hosted release work.

Default checks make no external/paid model calls. Real local Auth/Storage tests are opt-in via
`npm.cmd run test:authenticated` and `npm.cmd run test:e2e:authenticated`; generated configuration
must point to loopback. Authenticated browser tracing is disabled to avoid persisting credentials;
test fixture/credential containers redact their reprs. No claim of a full accessibility audit,
malware scan, provider evaluation or production readiness follows from these tests.

The current Google check proves only fail-closed behavior: local Supabase Auth reports
`external.google=false`, the public enable flag is absent and the rendered button is disabled.
This is not evidence of a successful configured-provider Google login.

[Continuous verification](ci.md) defines default and manually opted-in local integration jobs.
Its YAML/guards are locally validated; remote GitHub execution is unverified. Signal UI checks
add local font loading, responsive layout, loaded-campaign search, keyboard focus, reduced motion
and unavailable-WebGL recovery. Consult the ledger for the actual run rather than assuming test
source or CI configuration implies passing browser or Linux execution.

Optional `npm.cmd run test:media` uses local Docker and trusted synthetic FFmpeg fixtures, not paid
model APIs. `media:build` is required first; `media:fixture` prepares the decoded browser input and
`test:e2e:decoded` verifies real Auth/private Storage with decoded media but fixture providers.
Default/authenticated browser suites pin fixture media explicitly. Cancellation tests include real
container removal before a late start and while an input copy is held; daemon failure remains an
incomplete receipt. See the media ledger before interpreting a check as production proof.

Authorization checks cover absent/false/stale acknowledgments, verified receipt attribution and
atomic creation, immutable SQL provenance, legacy read-only history, new manifest binding,
withdrawal during decode/Check, lost authorization before input/publication, system expiry and
same-receipt cleanup retries. UI tests exercise notice load/retry, separate rights/acknowledgment,
stale-notice draft preservation and deliberate role-gated withdrawal. Record integrated and browser
results in the execution ledger; none of this substitutes for privacy/legal review of a live notice.

Read with [requirements](../product/requirements.md), [architecture](../architecture/overview.md), [data model](../architecture/data-model.md), [API contracts](../architecture/api-contracts.md), [privacy and threat model](../security/privacy-and-threat-model.md), [Meta readiness](../integrations/meta-api-readiness.md), and [roadmap](roadmap.md).

## 1. Completion and evidence

A feature is complete when its user outcome and failure behavior meet acceptance criteria, the relevant tests have actually run, access and privacy boundaries are verified, and the docs/evidence record names the build and limitations. A successful fixture run proves local orchestration; it does not prove a model's quality, latency, pricing, rights, availability or channel approval. Canonical invocation modes are `fixture`, `recorded`, and `live`; cached/fresh results and development/production environments are separate dimensions.

For each release keep a small receipt: commit/build ID, environment, migration and config version, provider mode, contract/test commands with time and results, evaluation dataset/prompt/rulepack versions, measured sample counts, known gaps, reviewer and rollback point. Receipts must not contain credentials, raw personal media, private URLs, full prompts or unredacted transcripts. Store consented fixtures securely outside public source control; commit fixture manifests and synthetic fixtures instead.

## 2. Test strategy and required invariants

Start with the smallest meaningful check; then test complete user flows in a local or dedicated
test environment with synthetic/consented fixtures. Never use production customer data or send
messages from a test to real shoppers. The current suite covers the first Check fixture slice,
real local Auth/private Storage, curated Find and the bounded initial creator guest flow. Rows
reaching product live providers, guest feedback/revision/withdrawal, refresh/crash upload recovery,
webhooks, live Try and Track remain required work. Exact-byte finalize replay and concurrent
guest-Storage-write/member-deletion ordering now have local regressions. One explicit synthetic Spark
transport smoke is separately verified and does not make product Check live.

| Layer | Concrete planned cases | Required invariant |
| --- | --- | --- |
| Domain/unit | Rule evaluation, pack validation, assessment aggregation, money rounding, consent transitions, timestamp offsets | Unknown evidence remains unknown; deterministic rules do not invent facts; fixed-point amounts and currency agree |
| Provider contracts | Each `Reasoner`/`Transcriber`/`Segmenter`/`TryOnProvider`/`CampaignDossier` fixture/recorded/live adapter; malformed/empty/truncated output, policy block, rate limit, timeout, usage missing | Normalized schema, bounded retry classification, preserved error/coverage/usage meaning; live syntax verified only after access; dossier's logical contract stays narrower even when it shares reasoning transport |
| Model/market eligibility | India end user, unknown country, conflicting account/deployment signals, policy-version change, stale queued request, alternative provider | Restricted Muse Image calls cannot reserve/enqueue/run/deliver; server policy fails closed for unknown eligibility while eligible modules continue; foreign hosting is not a workaround |
| Database integration | Tenant foreign keys, immutable manifests, inbox/outbox transaction, leases/heartbeats, spend reservation reconciliation | Atomic state changes; rollback does not leave billable orphan intent; lost leases cannot commit stale results |
| Auth/RLS/storage | Two tenants and brands; all roles; removed membership; expired JWT/grant; manipulated org/path/id; elevated worker scope | Both allow and deny cases pass; one tenant cannot infer/read/write/export another's data; guest cannot become reviewer |
| Upload/media | MIME spoof, oversized/duration cap, corrupt media, EXIF/GPS, missing audio, variable frame rate, rotated video, chunk boundary | Quarantined input cannot become trusted evidence; bounded isolation; correct timing and cleanup |
| Check/review | No speech, unsupported language, partial providers, invalid source IDs, reupload/reanalysis/sign-off race | No automatic approval; incomplete evidence blocks `no_issues_detected` and routine approval; stale manifest cannot be signed |
| Webhooks/channel | Signature invalid, duplicate event, simultaneous redelivery, out-of-order status, persistence outage, outbound timeout | Durable inbox before 2xx; duplicate handling does not duplicate orders/generation/messages; no unsafe blind resend |
| Jobs and recovery | Worker crash before/after provider call, lease expiry, cancellation, tombstone, poison message, retry exhaustion | Resume known safe work; fencing stops stale workers; ambiguous external side effects remain explicit |
| Spend/quotas | Concurrent jobs at cap, duplicate idempotency key, model retry, missing usage, FX/price change | Reservations plus settled/unknown spend stay within authorized envelope; no floating-point budget drift or double release |
| Retention/deletion | Original + derivatives + exports + caches + provider files; race with generation; failure/retry; restore | No new publishable personal data after tombstone; only necessary cleanup/receipt metadata may be written; per-copy receipt is honest; restore re-applies deletions before traffic |
| User E2E/accessibility | Create campaign, upload, check, review/fix/reupload; creator invitation fragment scrubbing, one-time exchange, cookie resume and revoked-session denial; Try consent/decline/retake, order attribution, disconnected provider | Responsive keyboard-accessible flows, progress/error states and visible fixture/recorded/live labels; no false success |

Actual commands and receipts are maintained in [implementation status](implementation-status.md).
Browser checks must inspect key interactions, mobile layouts, empty/error/loading states and
accessible labels rather than only screenshots.

## 3. AI evaluation before and after model access

Prepare a consented/synthetic labeled set before API access. Keep separate development and held-out sets; split by original creator/person/product/clip family so near-duplicate frames, edited captions and reused selfies do not leak across sets. Label exact rulepack/version, jurisdiction assumption, modality, issue span, expected assessment, evidence coverage and reviewer disagreement. Have two reviewers independently label high-risk issues, then adjudicate disagreements; counsel must review legal rule interpretation separately from technical annotation.

Cover clean, missing/late/unreadable disclosure, unsupported product guarantees, ambiguous claims, prohibited visual examples, no audio, failed transcription, code-switching, noisy speech, multiple resolutions/lighting, and malicious instructions in captions/on-screen text. Include negatives to measure false alarms and missing-evidence examples to measure abstention. None of this authorizes regulated health/finance launch before the rules and risks are reviewed.

| Evaluation | Proposed initial gate, unmeasured | How to report |
| --- | --- | --- |
| Check high-severity recall | Target at least 95% on the pilot's explicitly supported labeled cases; revise only through a recorded release decision | Numerator/denominator and confidence interval, by rule/language/modality; no blanket "95% compliant" claim |
| Check precision/false alarms | Target at least 85% finding precision overall, with per-rule breakdown | Count false positives, false negatives, abstentions and coverage failures separately; don't hide abstentions by dropping cases |
| Missing evidence safety | 100% of deliberately missing required-modality fixtures produce partial/review-required outcomes and no routine approval | This is a deterministic workflow gate; evaluate the upstream failure detector independently |
| Timestamp evidence | Evidence jump falls within the human-labeled interval/tolerance; initial visual tolerance target one second where sampling permits | Report offset distribution, source granularity and cases not meaningfully time-resolvable; no invented word-level timing |
| Try fidelity | Initial target at least 80% acceptable previews overall and at least 70% per sufficiently sampled pilot cohort/SKU slice | Two-reviewer score for product identity/shape/color, unwanted facial/body changes, artifacts and visible label; report counts, not just averages |
| Try critical safety/consent | No output on decline/withdrawal; no delivery when safety/quality checks fail; no hidden prompt path | Workflow tests plus adversarial review; a zero observed failure count does not prove zero real-world risk |
| Find proof | Correct authorized source, referenced segment and product/category match for each shown proof | Separate category resemblance from exact brand/SKU identification; no unsupported counterfeit/identity inference |
| Track attribution | All deterministic synthetic order/retry/refund fixtures reconcile to the documented attribution policy | Attribution coverage and conflicts, not causal uplift; discounted orders may not have been caused by a creator |
| Wonder campaign dossier | Every material claim cites a permitted campaign finding/source ID or explicitly says evidence is missing; no invented approval, financial result or cross-tenant fact | Validate source ownership, citation support, abstention, prompt injection, token/time/cost bounds and absence of privileged side effects |

These numbers are product quality hypotheses, not measured results or launch guarantees. The sample size must support the claim: 20 selfies or a handful of severe-issue clips cannot establish a narrow reliability interval. Report subgroup counts and uncertainty; suppress demographic claims on tiny samples. No biometric identity scoring or inferred sensitive cohort labeling. Use voluntary evaluation descriptors only when justified and consented.

Model-provided confidence is not a calibrated probability. Use explicit evidence availability and conservative routing first; select any confidence threshold against the held-out set and record false-positive/false-negative/abstention tradeoffs. A changing prompt, pack, preprocessing step or provider revision requires replay plus a held-out check before promotion. Keep a prior known-good version; require human approval to activate rule changes.

### Sampling and timestamp integrity

The source document suggests 5 fps SAM input as a cost optimization. This can miss brief disclosures and visual events; it is not evidence that an object never appeared between samples. Keep a time map from original presentation timestamps to normalized frames, sampled frames and audio chunks. Handle variable frame rate, clip trim offsets, dropped frames, rotation and chunk overlap without resetting time to zero. A frame index divided by five is valid only for the deliberately generated constant-rate sampling timeline, with the correct original offset.

Preserve turn-level transcription granularity if the provider offers only turns; do not fabricate word timestamps. Store modality/temporal coverage per finding. Before using a timing rule, test short flashes and boundary cases at the relevant source rate; use denser sampling or human inspection around uncertain spans. Report uncertainty and missing coverage, especially for source-draft rules such as disclosure in the first three seconds; the legal threshold itself requires primary-source review.

## 4. Reliability targets and telemetry

Initial internal pilot objectives below are aspirational and must be revised after the first live benchmarks. They are not customer SLAs.

| Indicator | Proposed objective | Measurement boundary |
| --- | --- | --- |
| Control API availability | 99% per calendar month during pilot | Valid eligible requests completing without server error; report dependency failures separately and don't silently exclude them from user impact |
| Non-media API latency | p95 below one second at agreed pilot load | Gateway receive to response, with auth/database work included |
| Try user-perceived latency | p50 near 20 seconds, p95 below 45 seconds | Consented valid photo accepted to preview actually delivered; record queue, provider, retry and channel components |
| Check turnaround | p95 below 90 seconds for a supported 60-second clip | Upload finalized to usable findings, including queue/preprocessing; partial results are not successful complete checks |
| Queue age | p95 ready-job wait below ten seconds at pilot load | Ready time to acquired valid lease, by job/provider class |
| Retention execution | All due app-managed Try copies deleted within the agreed 24-hour deadline | Receipt time to confirmed active-copy erasure; report provider and backup limitations separately |
| Recovery | Proposed RPO at most 24 hours and RTO at most four hours | Only adopt after the selected paid backup schedule and restore drill demonstrate them |

Use counters/histograms for accepted/completed/partial/failed jobs, queue age, lease expirations, duplicate webhook receipts, missing evidence, denied approvals, retry classes, deletion overdue/failure, provider usage, reservation exposure, spend per org/module, and preview quality rejection. Never use raw phone numbers, prompts, media, addresses or high-cardinality personal identifiers as metric labels. Correlate opaque request/job/tenant IDs in restricted logs; scrub error trackers and disable session replay on sensitive screens. Measure end-user latency independently of cached/recorded demo timing.

Initial alerts: deletion deadline at risk; active cross-tenant authorization anomaly; exhausted/unreconciled spend; sustained provider errors/rate limits; growing oldest job; repeated lost leases; inbox persistence failures; outbound ambiguity; backup failure. Each alert needs an owner, action and suppression rule before production; avoid alerting on every harmless retry.

Track eligibility denials by model, policy version and coarse permitted market code without storing unnecessary location data. Regularly review the official [geographic policy](https://dev.meta.ai/legal/geographic-use-policy); do not assume an API key means all models are available to all end users. On a restriction change, disable affected new work, cancel/reconcile pending calls and review undispatched results before delivery. A policy kill switch must be independent of the application's cosmetic availability toggle.

## 5. Jobs, retries, budgets, and external side effects

Use Postgres leased jobs and a transactional outbox initially. Claim ready rows atomically, store lease owner/expiry and a monotonically increasing fence/version, heartbeat long work, and accept completion only for the current lease. Limit attempts and total elapsed time; use exponential backoff/jitter and provider `Retry-After` where supported. Retry only documented transient errors, not malformed input, permission errors or safety rejection. Lease fencing protects database state; it does not undo a provider call that already happened.

Use a stable operation key across network retries and a separate attempt ID per real provider invocation. Send provider idempotency keys only where their contract supports them. Store external request IDs and a minimal call receipt before/after calls. When a timeout could have produced a billable output or sent a message, return the normalized provider error `OUTCOME_UNKNOWN`, preserve unresolved financial exposure, and reconcile by provider status/idempotency when available. This is not an ordinary retryable `PROVIDER_UNAVAILABLE` failure. Do not pretend at-least-once processing gives exactly-once external effects or blindly reissue ambiguous calls. Manual resolution is acceptable for a low-volume pilot.

Before queuing billable work, reserve a conservative maximum cost in a database transaction locking/atomically updating the tenant budget. Include all required modalities, permitted retry, tool/search fees if any, channel costs and price version. Check `settled + reserved + unresolved_exposure + new_reservation <= authorized_cap`, using disjoint buckets so the same exposure is not counted twice. If the data model combines reserved and unresolved amounts as `held`, its equivalent check is `settled + held + proposed <= cap`. Apply per-job, per-user/session and platform limits. Use integer minor/subminor currency units or exact decimals with one documented rounding convention; distinguish currencies rather than summing them.

Settle against actual reported usage when available; release only proven-unused reservations once. Unknown usage/cost remains reserved or recorded as conservative unresolved exposure, never zero. Handle expired reservations with a reaper that first checks job/provider state; a provider timeout is not proof no charge occurred. Disallow user-triggered bypass flags. If current prices/usage are unverified, live calls remain behind an explicitly configured test budget and operator gate, not published margin claims.

After retry exhaustion, place a job in a dead-letter state with safe error class, attempt count and resumable checkpoint. Show the user a truthful outcome and supported retry path. An operator may requeue only after fixing the cause, verifying remaining consent/authorization, checking deletion tombstones and acquiring a fresh budget reservation. Separate invalid media, unsupported features, provider outage and cancelled/deleted content; do not re-run already completed expensive stages without need.

During a provider outage: circuit-break only the affected port, retain permitted jobs within their TTL, cap concurrency and queue depth, show degraded status, and offer cancellation. Never substitute another provider with different data terms, training behavior or charges without an approved integration/policy. Fixture/recorded fallback must be visibly labeled and may use only authorized fixture data; it must not substitute someone else's selfie for a live shopper.

## 6. Deployment and recovery runbooks

Use separate local/test/pilot environments, provider keys, buckets, webhook secrets and callback URLs. Do not grant production credentials to preview deployments. Promote pinned dependencies/container images and versioned prompts/rulepacks; keep a record of actual model IDs and provider policy settings. Review changes to authorization, deletion, budgets, schemas, prompts and rulepacks with a second person where available. Use backward-compatible expand/migrate/contract schema changes; rehearse restoration and migration rollback/forward repair using synthetic data.

### Release

1. Record scope, build/config/migration versions, expected behavior and rollback point. Confirm the active account, region, provider mode and spend cap.
2. Run the relevant contract/integration/auth/state/evaluation checks and inspect UI flows. Review unresolved findings; never convert failures into passing receipts.
3. Back up according to the verified backup policy, apply additive migration, deploy API/worker/web compatibly, and run a synthetic smoke flow without real outbound recipients.
4. Release to internal users, then a small consenting pilot cohort. Monitor queue, errors, spend, deletion and output safety; stop expansion if a launch gate fails.
5. Roll back application/prompt configuration to the known-good compatible version or disable the affected feature. A rollback does not erase data migrations, revoke sent messages or reverse provider charges; use a documented repair for those.

### Provider incident or unexpected spend

Assign one incident owner. Stop new affected work with a feature flag/provider breaker and protect remaining budget. Preserve redacted request IDs, timing, price/config revision and reserved/settled exposure; inspect queue and ambiguous external calls before replay. Reconcile charges with provider receipts, explain affected user state, then resume a bounded canary. Do not expose private inputs in vendor tickets.

### Suspected data exposure or credential compromise

Contain the specific credential/route, revoke or rotate compromised keys/sessions/grants, and restrict access while preserving necessary minimal evidence. Identify tenant/data/time scope from audit records; assess provider and backup copies. The designated owner and counsel decide required customer/regulator communications based on actual jurisdiction/contracts; this document invents no universal notification deadline. Record containment, confirmed facts, unknowns, remediation, verification and follow-up. Do not delete relevant evidence indiscriminately or put raw exposed data into the incident report.

### Restore

Restore into an isolated environment using the recorded backup and compatible migrations. Reapply deletion tombstones and expired-consent/grant rules before any read access. Rotate recovered credentials where needed. Keep external sends and model calls disabled while reconciling inbox/outbox, leases, provider receipts and budget ledger; historical jobs must not auto-send or regenerate. Validate tenant isolation, latest applicable approvals and storage lineage, measure actual RPO/RTO, then return traffic gradually. Never claim a backup is recoverable until a restore has been demonstrated.

### Deletion backlog

Disable new sensitive intake if the retention promise cannot be met. Enumerate overdue artifacts by tenant/session without exposing their contents; retry safe deletions and inspect failed/provider-limited destinations. Prevent workers from recreating data through tombstone checks. Report actual status to affected users through the agreed support process and revise misleading product copy before resuming.

## 7. Launch gates

| Stage | Gate and evidence |
| --- | --- |
| Documentation/current local slice | Product scope, architecture, interfaces, source-verification gaps, privacy decisions and acceptance plan recorded; runtime claims require named local evidence in the implementation ledger. Hosted and live-provider behavior remains unmeasured. |
| Fixture build before credentials | Synthetic happy/error/partial flows, deterministic approval guard, two-tenant policies, job/budget/idempotency/deletion invariants implemented and tested; visible fixture-mode labels |
| Live API spike after access | Real account/model/market eligibility, retention/training terms, auth/rate limits, output/usage fields and measured cost/latency verified; consented bounded evaluation and provider receipts; channel/commerce permissions separately checked; India Muse Image remains disabled under the currently reviewed policy |
| Hackathon demo | Explicit fixture/recorded/live behavior; consent and AI labels; no hidden legal/accuracy/24-hour-provider-erasure claims; permitted assets; capped one-at-a-time live interactions and safe backup demo |
| Small external pilot | Passing critical boundary tests; documented evaluation results/known gaps; approved privacy/retention notice and reviewed rulebooks; real deletion/restore drill; support contact, incident owner, opt-out and kill switches |
| Paid expansion | Evidence of user value, measured unit economics including retries/support/channel costs, billing reconciliation, reviewed customer terms, measured reliability and capacity, unresolved-risk acceptance; no enterprise compliance badge implied |

Critical authorization, approval-integrity, consent, deletion or uncontrolled-spend failures block real-data launch regardless of a polished demo. Low statistical confidence in model quality narrows supported use and increases human review; it does not justify marketing an unmeasured accuracy number.
