# Implementation roadmap

Status: local fixture slice, curated Find, India Try gate, initial creator guest draft foundation and
explicit creator-feedback publication implemented
on Supabase Postgres; server-only Meta catalog and bounded Spark synthetic-smoke adapters implemented,
unit-tested and account-verified; updated 2026-10-28.
local Supabase authentication/private Storage and restricted API/worker credentials are now implemented.
Public hosted rollout and production media isolation remain gates. Later creator revision,
exact-source withdrawal and a test-only Track ledger are implemented. Anchored
retention, bounded local media decoding/cleanup and versioned processing authorization/withdrawal
are implemented. Google entry remains disabled by default; workspace storage accounting and bounded
Signal motion are implemented and locally verified. The draft local notice is not a live-provider
or legal activation approval.
User-confirmed: startup quality, India plus international capability
gating, useful breadth across Meta models, access expected October 26. Official eligibility remains
unknown; dates below are planning windows, not commitments.

## 1. Preparation through October 25

The architecture/documentation baseline and first local fixture implementation now exist. Preserve
this pre-event work record and obtain official rules before assuming any code or asset can be
submitted.

Prepare non-code assets where permitted: consent/rights inventory, synthetic scenario descriptions, rulebook source review, expected labels, pilot interview questions, demo storyboard and capability checklist. Do not put personal media, secrets or signed URLs into a public repository.

Assign owners for product/UX, full-stack/backend, AI evaluation/integrations and privacy/rule review. A one-person team should reduce integration breadth rather than weaken approval, consent or tenant boundaries.

## 2. First implementation slice

**Goal:** a brand user creates a campaign, submits a synthetic/authorized draft, sees timestamped fixture findings, requests a revision, and a reviewer signs off the exact complete version. Everything is explicitly fixture mode until live contracts pass.

| Step | Outcome | Acceptance evidence |
| --- | --- | --- |
| S1: Scaffold | Next.js web, shared Python backend API/worker entrypoints, dependency locks, local config and CI | Documented run commands actually work; health checks and baseline type/lint/unit checks pass. |
| S2: Workspace | Supabase Auth, migration/RLS/storage policies, organization membership/roles, seed synthetic campaign | Cross-tenant ID and role denial tests cover member, revoked member and worker paths. |
| S3: Submission | Narrow signed upload, quarantine validation, immutable media/caption versions | Invalid media and unauthorized finalization fail; source hash and source-time metadata verified. |
| S4: Durable job | Transactional command, idempotency, budget reservation, leases, stage outcomes and cleanup refs | Duplicate/concurrent command and worker restart do not duplicate a billable logical stage or publish stale output. |
| S5: Check fixture | Typed transcript/visual/track fixtures, draft brand-policy rules, complete/partial findings | Missing required evidence cannot produce clean assessment or routine approval. |
| S6: Review | Timeline, finding decisions, fix draft, reupload/version comparison, reviewer approval | Unauthorized role, stale manifest and reupload race cannot inherit approval. |
| S7: Trust gates | Consent/rights, redacted logging, retention/deletion and safe usage view | Delete during work blocks delivery and cleans all test derivatives; no sensitive payloads in telemetry. |

Implementation status: S1's local runtime (not remote CI) and the fixture portions of S3-S7 are implemented and covered by local
tests on SQLite and local Supabase Postgres. S2 has private runtime persistence and verified tenant,
revoked-membership and direct-mutation denial tests, real local bearer sessions, separate restricted
API/worker roles, and private Storage/deletion. Anchored cleanup now has its own restricted role,
durable retries and recoverable receipts. Bounded decoded validation now preserves measured time
and container deletion accounting. Versioned authorization now requires separate acknowledgment,
binds immutable receipts in new manifests, preserves legacy history without fabricated consent and
withdraws through the existing cleanup workflow. The Signal visual refresh, local CI configuration,
disabled-by-default Google entry, workspace storage allowance and bounded motion continuation are
implemented; remote CI execution and live Google authentication remain unverified. Curated Find
and the India Try policy gate are implemented. The creator portal has its isolated invitation,
exchange, submission view, guest-attributed upload/receipt and initial version. Exact-byte replay
after finalization, the late Storage-write/deletion race and explicit allowlisted feedback
publication/deletion scrubbing, later immutable revision and exact-source withdrawal are closed. See
[implementation status](implementation-status.md) for evidence and the exact next step.

Relevant requirements: VCH-FOUND-01, CAMP-01/02, MODEL-01/02, CHECK-01 through CHECK-10, AUDIT-01, TRUST-01/02/03, OPS-01 and ACCESS-01. Prefix omitted after first reference.

Do not start every integration while this flow is incomplete. Fixture success proves the application workflow only; it does not establish live model capability or compliance accuracy.

## 3. October 26: access and eligibility day

Follow the [activation checklist](../integrations/meta-api-readiness.md#8-october-26-activation-checklist). Recheck geographic policy, rules, actual model catalog/team limits, Standard settings, file lifecycle and credits. Record sanitized pass/fail evidence by family/account/region.

Use tiny synthetic requests first. Establish the exact tested SDK payload/schema/stream parser. If keys are delayed, continue permitted fixture workflow work and leave capability status awaiting_access. If a capability is policy-restricted, do not keep retrying or route around the restriction.

**Meaningful five-family goal:** live Spark visual reasoning, Voice transcription and SAM evidence; bounded Wonder campaign dossier; Image preview only with permitted operator/deployment/end-user eligibility and a passed fidelity/privacy gate. A skipped family has a visible reason, not a manufactured call.

## 4. Proposed October 26 to November 4 sprint

| Window | Focus | Exit gate |
| --- | --- | --- |
| Oct 26 | Access/policy smoke tests and short risk spikes | Current readiness matrix; file deletion check; measured cost/latency baseline. |
| Oct 27–28 | Replace Check fixture stages with live adapters | Source-aligned evidence; live failure paths; role/version-bound review still works. |
| Oct 29 | Check evaluation and creator revision path | Held-out labels, missing-evidence safety, reviewer feedback and honest precision/recall report. |
| Oct 30 | Wonder dossier + curated Find | Every summary citation resolves; creator evidence authorized; outreach remains a draft. |
| Oct 31–Nov 1 | Eligible-market eyewear Try spike and web flow | Consent, eligibility, retry ceiling, fidelity/identity rubric, labels and anchored deletion tested. Otherwise show unavailable/synthetic preview explicitly. |
| Nov 2 | Track + one authorized channel/commerce integration if ready | Verified event/order/refund dedup, deterministic attribution, separate test/live metrics. |
| Nov 3 | Security/quality pass, UX polish, recovery/demo rehearsal | Critical acceptance scenarios, responsiveness, no raw-data logs, deletion/worker restart drill. |
| Nov 4 | Freeze, final recording, submission buffer | Honest model/live/fixture inventory, measured evidence, limitations, rule/rights disclosures and reproducible README. |

The organizer lists November 4, 21:00 ET as the submission deadline; keep a several-hour buffer and recheck updates. The page's EST/ET wording is not a reason to assume a fixed local-time conversion. [Official event](https://cerebralvalley.ai/e/meta-ai-developer-hackathon)

Parallel owners can overlap independent steps; a single developer should cut breadth. This roadmap recommends the order rather than promising all integrations in ten days.

## 5. Scope cuts and demo integrity

If behind: cut billing, public API, automatic outreach, Instagram comment-to-DM, broad discovery, audit PDF and enterprise features. Keep consent, tenant isolation, human approval, version binding, budget controls, clear provenance and cleanup.

Minimum credible demo: complete campaign → draft → live or explicitly fixture Check → evidence → human review → revised version. Add a cited Wonder dossier and curated Find if ready. Track can show verified test events; never label them revenue. Try is live only for eligible operators/users and passed quality; first-party web does not bypass Image policy.

Record the actual adapter calls and provider request IDs in redacted traces. Muse Code usage is build tooling, not proof the application called Wonder or another runtime model. Do not claim all five families work unless the evidence exists.

## 6. Startup pilot, first 30–90 days

**Days 1–30 after event:** validate a single buyer/workflow with a small opt-in cohort, finish onboarding and recovery, legally review the applicable rule pack, agree retention/disclosures, test backups/restore and measure review time/cost. No regulated-customer launch solely on draft rules.

**Days 31–60:** add one demanded integration at a time (Shopify or messaging after permissions), improve creator revision UX, collect authorized error labels and implement support/usage controls. Begin paid pilots only after full cost and contractual terms are known.

**Days 61–90:** validate paid retention, repeated use, team collaboration, reliable exports, billing/refunds and measured operating margin. Broaden rules/markets/categories only after one workflow demonstrates value.

Do not treat SSO, SOC 2, payout automation, data residency or a marketplace listing as present. They are separate investment decisions with evidence and ownership.

## 7. Extension gates

| Extension | Build when | Prerequisite |
| --- | --- | --- |
| Full official/licensed Find | Curated evidence is useful and customers need scale | Data rights, quota/cost, measured exact/category-match quality. |
| Instagram/WhatsApp | Channel friction blocks validated workflow | Correct account permissions, current messaging rules, signatures and opt-in. |
| India Try alternative | Customers demonstrate preview demand | Permitted provider + hackathon eligibility, privacy disclosure, quality and unit economics. |
| More regions/rulebooks | Real customer need | Source applicability and qualified review, version/effective-date strategy. |
| Apparel/decor Try | Eyewear evaluation and repeat usage pass | Category-specific fidelity/safety tests; no fit promise. |
| Open-weight Spark Open/Glimmer | Measured privacy, cost or latency gain warrants it | License, hosted/compute resources, benchmark and safe adapter integration. |
| Rulebook research assistant | Maintaining reviewed packs is a bottleneck | Allowlisted official sources, citation/diff evidence, human publication approval. |
| Billing/public API/agency permissions | Paid usage and integration needs are established | Entitlements, quotas, invoices, credential lifecycle and support ownership. |

## 8. Documentation completion versus app completion

Documentation and architecture now describe the first implementation slice. Local application and
database checks are recorded in [implementation status](implementation-status.md). Application
readiness still requires hosted bootstrap/credential operations, the guest mutation lifecycle, reviewed notices and
privacy-rights operations, live contract checks, measured model evaluation and exercised
operational controls. Local decoded media and workspace notice withdrawal do not close those gates.
