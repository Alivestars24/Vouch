# Vouch product requirements

Status: **fixture Check, curated Find, India Try gating, test-only Track, initial/later guest drafts
and explicit creator-feedback publication are
implemented; broader product baseline remains proposed and founder
validation is required.** Local workflow tests do not establish live integration, model evaluation,
customer commitment or legal approval. SQLite and Supabase Postgres fixture execution pass the same
invariants. Updated 2026-10-28; see
[implementation status](../engineering/implementation-status.md).

Implemented local foundation now includes real Supabase bearer sign-in, current membership/roles,
separate restricted API/worker logins, private media upload/read/delete and retryable deletion
receipts. This advances VCH-FOUND-01, TRUST-01/02 and ACCESS-01; it does not implement self-service
organization onboarding. Guest invitation, recovery/renewal, exchange, scoped session, private
upload/finalize, guest-attributed processing receipt and initial immutable version publication are
implemented locally. Anchored retention cleanup is implemented;
its verification is tracked separately in the ledger and
[retention contract](../architecture/retention-worker.md).
Provider execution remains deterministic fixtures. See the
[authenticated contract](../architecture/authenticated-foundation.md) and execution ledger.

The accepted [Signal visual system](../../design.md), refined on 2026-10-26, governs the member
workspace, campaign workbench, sign-in and creator portal. Its editorial overview may summarize
only API-returned campaigns, next actions and markets; it must not recreate the reference image's
revenue, reach, creator, compliance or Try results. Campaign search filters loaded records only;
counts reflect returned actions, not invented minimums or live business metrics. Optional
decorative illustration and WebGL must not block a real task or imply analysis.
The [creator portal architecture](../architecture/creator-portal.md) has a verified initial-draft,
later immutable revision, exact-source guest withdrawal and explicit member-selected feedback
publication. Curated Find records the exact compatible evidence used for a campaign roster
decision; broad social discovery remains outside the authorized surface.

The Track MVP implements tenant-scoped, roster-bound test clicks, orders and refunds with stable
external IDs, explicit currencies, raw event evidence and separate test/live summaries. It does
not implement live commerce/webhook intake, tracked redirects or causal lift/ROI claims.

Accepted 2026-10-24 extension: [Google entry, storage and motion](../architecture/oauth-storage-motion.md)
advances FOUND-01/TRUST-01/ACCESS-01. Google is a visible, disabled-by-default option and never grants
workspace authority. The user reports Google Cloud setup, but the checked local Supabase Auth state
still has the provider disabled and the frontend availability flag is absent. Storage must enforce
an atomic 500 MB workspace allowance, show reservations/pending cleanup, and preserve immutable
originals. Loading orbs and scroll-responsive 3D must remain optional and follow actual state.
Supabase's published 500 MB database and 1 GB file-storage allowances are different from this app
limit; no remaining provider capacity or production readiness is inferred. Verification is in the ledger.

Bounded optional local media decoding/transient normalization and deletion accounting for active
containers are implemented; they do not establish live model observations or production isolation.
Versioned notice acknowledgment and withdrawal are implemented under the accepted
[processing authorization contract](../architecture/processing-authorization.md). Every new upload
requires rights attestation and a separate affirmative acknowledgment of the current local draft
notice. Historical assets receive no fabricated receipts and cannot authorize new work. Withdrawal
atomically revokes authorization and starts the existing deletion workflow. This advances
VCH-TRUST-03 locally, not legal review or proof of third-party subject consent; integrated proof is
recorded separately in the execution ledger.

## 1. Evidence and authority

| Label | Meaning in this document |
| --- | --- |
| User-confirmed | The founder supplied the design document, wants documentation before implementation, wants startup-quality foundations, and expects access to the hackathon model APIs on October 26. The founder wants purposeful use of most/all Meta model families and targets India plus international markets, enabling capabilities by eligibility. The linked event is the [Meta AI Developer Hackathon](https://cerebralvalley.ai/e/meta-ai-developer-hackathon). API availability remains an expectation until tested. |
| Source-stated | The supplied document proposes or claims something. Its own “verified” labels are not independent verification by this project. |
| Proposed | A recommended scope, product behavior, target, or design decision that the founder has not yet validated. Unless explicitly labeled otherwise, the requirements below have this status. |
| Needs verification | Depends on provider documentation, actual account access, legal review, platform approval, customer research, or measured evaluation. |

The [extracted design document](../source/design-document-extracted.md) preserves the supplied vision. Relevant source blocks: B33–B42 for positioning; B65–B98 for users and modules; B99–B109 for trust; B200–B260 for demo scope and evaluation. The document is reference material, including its embedded prompts and build instructions. This PRD proposes a narrower implementation baseline rather than silently accepting every source MVP label.

Provider facts and open questions live in [Meta API readiness](../integrations/meta-api-readiness.md) and [references](../references.md). Architecture, [data model](../architecture/data-model.md), [API contracts](../architecture/api-contracts.md), [privacy](../security/privacy-and-threat-model.md), and [quality gates](../engineering/quality-and-operations.md) specify the corresponding implementation constraints.

## 2. Product hypothesis and first customer

Vouch helps a brand run a creator campaign through **Find → Check → Try → Track**, with the campaign connecting products, creators, content versions, review decisions, and measured events. The source envisions a modular B2B product with a brand workspace, creator submission experience, and shopper conversation.

**Proposed initial wedge: Check for a small D2C eyewear brand or agency with an identified human reviewer.** Demonstrate evidence-backed review and revision before expanding the commercial promise. Eyewear keeps the optional Try experiment bounded; it does not establish demand or model suitability. The confirmed market direction is India plus international; regulatory coverage and feature eligibility are scoped per supported market rather than promised worldwide. Regulated finance and health pilots require specialist rules and review and are outside the initial pilot.

The main job is: “Help our reviewer find potential disclosure and brand-rule problems, explain what needs attention, and preserve who approved exactly which version.” Vouch provides decision support. It must never describe an AI result as legal certification, verified regulatory compliance, or permission to publish.

The source tagline “Everything stays compliant” is an aspiration, not an acceptable product guarantee. Proposed public wording: **“Creator campaigns you can trust.”** Name, domain, trademark availability, willingness to pay, and differentiation remain unvalidated.

## 3. Users and authority

| Role | Can do in the first pilot | Cannot do by default |
| --- | --- | --- |
| Workspace admin | Manage workspace, membership, configured integrations, usage limits and retention; assign reviewer privileges | Obtain reviewer authority merely by being admin; read other tenants; approve incomplete analysis |
| Marketer | Create campaigns, manage a curated roster, submit content, request checks, prepare fix messages and inspect authorized reports | Approve content without reviewer membership; change active rules silently; send messages without an explicit user action |
| Reviewer | Inspect evidence and rule sources, record finding decisions, request changes, approve or reject the exact checked version | Convert partial or failed processing into a clean result; edit historical evidence or someone else's approval event |
| Viewer | Read authorized campaigns, reports and review records | Upload, edit, approve, send messages or change integrations |
| Creator guest | Through a scoped, expiring invitation, submit a draft, see permitted feedback and provide a revision | Browse the workspace, other creators, shopper data, costs or unrelated media |
| Shopper | If Try is enabled, consent, select a product, submit their own permitted photo, receive a labeled preview and request deletion | Supply arbitrary generation prompts or access another shopper's session |

One person may hold multiple explicit roles in a small pilot. The audit record must still identify the authenticated human actor. A creator invitation is a narrowly scoped credential, not an anonymous public media inbox. Agency multi-brand access is a later extension; tenant isolation is a foundation from the first implementation.

## 4. Scope and delivery boundaries

| Stage | Included | Gate to advance |
| --- | --- | --- |
| Documentation now | Product/design baseline, architecture, contracts, security model, evaluation plan, fixtures specification and open-decision register | Founder validates the proposed wedge and documentation; event rules and pre-event work restrictions are checked before implementation |
| API-independent implementation after documentation | Campaign and role skeleton, immutable media versions, review workflow, curated Find, deterministic test Track, adapter contracts and visibly labeled fixture mode | Relevant quality and isolation checks pass; no claim that fixture execution validates a provider |
| API access validation, expected October 26 | Confirm actual model availability, payloads, privacy terms, costs and limits; run bounded capability/evaluation spikes | Verified capabilities are recorded and a repeatable Check pipeline passes its release gates |
| Hackathon demo | One campaign, a small curated creator set, a new authorized draft checked with evidence, revision and human review, and an honestly labeled attribution demonstration | Core path works without developer intervention; cached/demo/live behavior is disclosed; required privacy and failure paths work |
| Controlled pilot | Small invited customer cohort, reviewed rule pack, measured Check quality, access controls, deletion, operational runbook and support owner | Pilot entry criteria in [quality and operations](../engineering/quality-and-operations.md); no production promise based on a demo alone |

**Recommended demo priority:** Check is the required end-to-end path. Find is a curated, rights-cleared list with evidence rather than broad social discovery. Track records a small, deterministic event trail. An on-demand campaign evidence dossier provides a meaningful bounded role for Wonder. Eyewear Try is a capability spike and demo extension only after geography, provider access, fidelity, privacy and delivery gates pass. This sequencing is a recommendation for founder validation, not a confirmed change to the four-module vision or the founder's model-coverage goal.

### Purposeful Meta model coverage

| Hosted family | Proposed bounded role | Required proof before claiming live use |
| --- | --- | --- |
| Spark | Visual/structured evidence reasoning and rule-mapped Check findings; curated Find relevance | Supported account/model contract, provenance, evaluated evidence quality and actual call records |
| Voice Transcribe | Speech turns for Check, with documented timestamp precision and tested languages | Actual supported audio contract and measured transcription quality |
| SAM | Product/concept evidence and segmentation, with sampling limits exposed | Evaluated concept reliability; never use concept presence as proof of SKU fidelity |
| Wonder | On-demand campaign evidence dossier synthesizing authorized stored findings and events, with record citations and human review | Verified access, bounded read-only invocation, citation validation, metered usage and evaluated summaries |
| Muse Image | Eyewear AI preview only where provider policy permits and fidelity/privacy gates pass | Deployment/operator/end-user eligibility, actual access, consent, supported privacy configuration and per-SKU quality gate |

This targets all five hosted families for meaningful roles without inventing calls or making every family a mandatory dependency of each workflow. An unavailable family has an explicit capability state and an evaluation/readiness task. Open-weight families such as Spark Open/Glimmer are optional future benchmarks, not extra runtime dependencies merely to increase model count.

**Policy constraint:** Meta's [Geographic Use Policy](https://dev.meta.ai/legal/geographic-use-policy), section 2.2, restricts Muse Image access from India and availability to end users in India. The India experience must not make live Muse Image calls; show `policy_restricted`, distinct from `awaiting_access`. Evaluate deployment, operator and end-user eligibility, fail closed when eligibility is unknown, and never route around restrictions. An alternative provider can be designed behind an adapter but is not selected or approved here; its terms, privacy, quality and hackathon acceptance require separate verification. Synthetic fixture previews must be labeled as such and never attributed to a live Muse Image call. See the [verified readiness record](../integrations/meta-api-readiness.md).

Not in the first demo: automated cold outreach, general-purpose chat, Instagram-wide search or scraping, live social publishing, automatic rule publication, commission payouts, multi-country legal coverage, billing, enterprise SSO, dedicated mobile apps, apparel fit/size promises, revenue-lift claims, or a cross-brand creator reputation score. WhatsApp, Instagram, Shopify, YouTube and model APIs have separate access requirements; access to the hackathon models does not imply access to these services.

## 5. Functional requirements

Priority meanings: **Core** is required for the recommended Check-first demo; **Foundation** is required before real pilot data; **Conditional** ships only after its stated gate; **Later** is intentionally outside the first demo. All remain proposed.

| ID | Priority | Requirement and acceptance boundary |
| --- | --- | --- |
| VCH-FOUND-01 | Foundation | Every campaign, media asset, job, finding, approval, event and export belongs to a workspace. Server-side authorization must enforce workspace and role scope, including background jobs and signed media access. Guessing another object's identifier never grants access. |
| VCH-CAMP-01 | Core | Create a campaign with name, objective, product, curated creators, applicable market and pinned rule-pack versions. Show rule-pack status and source provenance. A draft/demo pack is never presented as legally reviewed. |
| VCH-CAMP-02 | Core | Show actionable tasks such as “2 drafts awaiting review”; distinguish empty, unavailable, loading and zero. Workspace cards must not invent live sales, integrations, creator counts or model results. |
| VCH-MODEL-01 | Core | Route model functions through documented adapters. Record canonical invocation mode `fixture`, `recorded` or `live`, and display execution provenance on every result. Cache-hit/freshness metadata and unavailable capability state are separate from invocation mode. A fixture/recorded run never silently substitutes for a failed live call. Record prompt, model and adapter versions. |
| VCH-MODEL-02 | Foundation | Keep provider-family capabilities and policy eligibility explicit per deployment/operator/end-user context. `policy_restricted`, `awaiting_access`, unsupported input and degraded service are different states. Block restricted/unknown-eligibility Image requests before personal-data upload/provider calls; no automatic provider failover with personal images. |
| VCH-FIND-01 | Core | List explicitly curated creators and authorized proof assets with source, rights/permission status and evidence timestamp. A category match is not proof of an exact brand/SKU match. An unavailable or unreviewed match is labeled accordingly. |
| VCH-FIND-02 | Core | Add a creator to the campaign roster and prepare a copyable outreach draft. No external message is sent merely by opening, generating or accepting the draft. |
| VCH-CHECK-01 | Core | Submit an authorized video and caption to a campaign. Validate supported type, size and duration before processing; retain content hash, caption snapshot/hash, uploader and source. A revision creates a new immutable version rather than overwriting the reviewed asset. |
| VCH-CHECK-02 | Core | Extract or ingest time-aligned speech, on-screen text and visual observations with source/modality and precision. Missing speech, failed OCR, uncertain segmentation, inaudible turns or absent model capability are explicit coverage gaps; they cannot mean “no issues.” |
| VCH-CHECK-03 | Core | Evaluate only pinned, applicable rule versions. Each rule has an identifier, scope, status, source citation, effective/version metadata and reviewer/owner. Distinguish brand-policy checks from legal rules. Source examples such as a three-second disclosure threshold are draft policy examples, not verified law. |
| VCH-CHECK-04 | Core | Return findings with rule ID/version, severity, short evidence quote or description, timestamp range or caption location, evidence source, uncertainty and suggested next action. A claim without sufficient evidence is marked for review; a model must not invent a rule, citation or precise timestamp. |
| VCH-CHECK-05 | Core | Keep processing, machine assessment and human decision separate, using the state model below. `no_issues_detected` means no issues found within assessed coverage, not compliant or approved. Partial, failed and unassessed runs cannot produce a clean assessment or be approved. |
| VCH-CHECK-06 | Core | Reviewers can accept, dismiss with rationale, or flag an individual finding as incorrect/uncertain. Decisions append an actor/timestamp event while preserving the original model observation. A finding decision is not a content approval. |
| VCH-CHECK-07 | Core | Only an explicitly authorized reviewer can approve the exact eligible content/caption version after complete analysis and required finding decisions. Save reviewer identity, time, content/caption hashes, analysis ID and rule/model/prompt versions. Unresolved required blockers prevent approval. Approval does not publish content. |
| VCH-CHECK-08 | Core | A reupload or caption change creates a new version requiring review. A materially changed rule pack or analysis creates a new review context; historical decisions remain readable but do not approve the new context. Never carry approval forward silently. |
| VCH-CHECK-09 | Core | An authorized workspace member can download a readable report only for the currently approved exact version. It includes immutable hashes, reviewer/time/rationale, pinned check provenance, evidence, finding decisions and limitations. Revoked, superseded, deleted or incomplete approval state cannot produce a current report, and the report never claims legal certification or publication. |
| VCH-CHECK-09 | Core | Prepare a timestamped fix-request draft; make the creator submission link explicit and scoped. The first demo may use copy/share performed by the user. If sending is implemented later, require an explicit send action, delivery state and idempotency. |
| VCH-CHECK-10 | Core | Display a revision comparison: added, resolved, persisted and incomparable findings, evidence coverage and version provenance. “Not detected in the new run” is not “fixed” when the corresponding modality failed or the rule/prompt changed incompatibly. |
| VCH-AUDIT-01 | Core | Preserve append-only review history and a readable review summary with provenance and limitations. A later PDF is an export of those records, not a new authority. Exports are permission-checked and exclude shopper photos and unnecessary personal data. |
| VCH-WONDER-01 | Conditional | Offer an on-demand, bounded, read-only campaign evidence dossier using Wonder where access permits. Synthesize only authorized stored record IDs and time-bounded facts, validate citations, separate observed facts from recommendations, and require human verification before external use. No sending, publishing, rule changes, approvals, invented metrics or cross-tenant retrieval. Enforce an invocation budget and show stale/failure provenance; dossier failure never breaks Check/Track. |
| VCH-TRY-01 | Conditional | Enable eyewear Try only for eligible deployment/operator/end-user regions and approved SKUs after a documented fidelity/safety spike and supported model/privacy configuration. Muse Image stays disabled for India use. Gate the module when policy, access or quality is inadequate; the core Check demo remains usable. A web mobile flow may replace unavailable messaging access but cannot bypass model-region restrictions. |
| VCH-TRY-02 | Conditional | Before any photo upload/provider processing, explain purpose, provider involvement, retention, AI limitations, optional nature and deletion; collect explicit consent plus adult self-attestation and photo-use permission. Do not describe a model's age estimate as age verification. No face identification or biometric matching. |
| VCH-TRY-03 | Conditional | Use constrained product templates, safe input checks and a product-quality gate. Decline unsafe/multiple-face/unsuitable inputs or give neutral retake guidance. Permit at most one bounded generation retry per request; do not create an unbounded cost loop or freely editable prompts. |
| VCH-TRY-04 | Conditional | Every displayed or downloaded preview has a visible “AI preview” label and “Fit, size and exact appearance are not guaranteed.” Keep the product reference beside the output. A failed quality gate never delivers a misleading success. Sharing is user initiated. |
| VCH-TRY-05 | Conditional | Show progress, cancel, timeout and recoverable error states; prevent duplicate preview generation from retried messages. Expired/revoked sessions cannot accept new photos or deliver stale results. A deletion request cancels pending processing and blocks subsequent preview delivery. |
| VCH-TRACK-01 | Core | Associate tracked links/events with campaign and creator and record event source and environment. Clicking a buy link is not an order. Unknown or conflicting attribution is shown as unknown/ambiguous, not guessed by a model. |
| VCH-TRACK-02 | Core | Use the deterministic attribution policy in the API/data contracts, including duplicate webhook handling and cancellation/refund semantics. A test order is labeled test; fixture revenue is never mixed with live revenue. Expose raw supporting events to permitted reviewers. |
| VCH-TRACK-03 | Core | Show counts with named definitions, denominators, time ranges and freshness. Only display conversion rates when numerator and denominator are meaningful. Do not claim causal lift or total campaign ROI from attributed orders alone. |
| VCH-TRUST-01 | Foundation | Make retention and deletion behavior user-visible. Proposed Try default: delete first-party source photos and generated previews within 24 hours of receipt, or sooner on request; deletion covers derivatives and scheduled work. Verify provider-side retention separately and disclose limits. A pending or failed purge cannot be labeled completed. |
| VCH-TRUST-02 | Foundation | Only send real data to a provider after its processing/training/retention settings and terms are verified and documented. Source statements about “Standard” mode are unverified until then. Keep secrets, raw photos, signed media URLs and full prompts containing personal data out of analytics and general logs. |
| VCH-TRUST-03 | Foundation | Record consent notice version, purpose, timestamp and revocation; preserve only the minimum lawful audit metadata after deletion. Human privacy rights and tenant isolation apply equally in fixture, demo and live modes. |
| VCH-OPS-01 | Foundation | Enforce per-workspace usage limits, bounded job retries and cancellation. Record errors and observed cost/units without fabricating a dollar estimate when pricing is unknown. The UI identifies failed stages and safe next actions. |
| VCH-ACCESS-01 | Core | Core journeys work by keyboard, expose accessible names/status updates, use text/icons beyond color, and remain usable on mobile. Timestamp findings link to accessible evidence; provide transcript/caption alternatives where available. See [experience](../design/experience.md). |

## 6. Check state and approval semantics

These are three independent fields, not interchangeable statuses. Their canonical contracts are maintained in [API contracts](../architecture/api-contracts.md).

| Field | Allowed values | Product meaning |
| --- | --- | --- |
| `analysis_status` | `queued`, `running`, `completed`, `partial`, `failed`, `cancelled` | Whether the required processing and evidence stages finished. `completed` alone does not imply a positive outcome. |
| `machine_assessment` | `no_issues_detected`, `fixes_suggested`, `potentially_blocking`, `human_review_required`, `not_assessed` | What the automated process concluded within its coverage. Model confidence is not a calibrated probability or legal assurance. |
| `review_status` | `unreviewed`, `changes_requested`, `approved`, `rejected`, `superseded`, `revoked` | The recorded human workflow state for the precise review context. |

An API/AI process may write the first two fields; it cannot create an approval. A reviewer action appends a decision after authorization and eligibility checks. Approval eligibility requires completed required analysis, unchanged content/caption and pinned versions, and no unresolved required blockers. A deliberately unavailable modality cannot be silently waived while showing a complete multimodal check; a narrower, explicitly scoped check requires its own documented coverage and release gate.

Approval is an auditable brand review decision, not an assertion that every applicable law or platform policy was examined. A later revocation preserves the original event and adds who revoked it and why. Changes to content, caption, applicable pack or review context mark the old context historical/superseded and require a new review; they never rewrite the historical approval.

Proposed severity is `critical`, `major` or `minor`. Evidence uncertainty is a separate concern: a high-severity suspected issue may still be uncertain and need human review. “Fix” suggestions must not promise legal sufficiency, invent substantiation, or automatically replace claims in published media.

## 7. Critical acceptance scenarios

Every scenario is a future acceptance check, not a claim that it has passed.

| ID | Scenario | Required result | Requirements |
| --- | --- | --- | --- |
| AC-01 | Marketer or another tenant attempts approval directly through an API | Denied server-side; no approval event; scoped audit event where appropriate | FOUND-01, CHECK-07 |
| AC-02 | AI returns no findings but transcription fails | Coverage gap and `partial`/review-required state; no clean summary or approval eligibility | CHECK-02, CHECK-05 |
| AC-03 | Model output includes a rule ID not in the pinned pack, an invalid time range or an unsupported quote | Reject/flag invalid output; preserve failure provenance; never invent evidence to make it displayable | CHECK-03, CHECK-04 |
| AC-04 | Reviewer finishes all required decisions and approves a complete run | Approval binds exact hashes/versions and named actor; UI still distinguishes machine assessment from human decision | CHECK-06, CHECK-07 |
| AC-05 | Approved creator draft is reuploaded or its caption is edited | New version is unreviewed; old approval is visibly historical; old and new media cannot be confused | CHECK-01, CHECK-08 |
| AC-06 | New version has no spoken finding because audio extraction now failed | Comparison says evidence unavailable/incomparable, never “resolved” | CHECK-02, CHECK-10 |
| AC-07 | Live provider fails while fixture/cached output exists | Explicit user-selected fallback with provenance; no silent live-success label | MODEL-01 |
| AC-08 | Expired or tampered creator invitation is reused | Access denied with a safe renewal path; no unrelated media or workspace metadata disclosed | FOUND-01, CHECK-09 |
| AC-09 | Shopper declines consent, cannot confirm adulthood, or leaves before photo submission | No photo collection/provider call; product browsing or exit remains available | TRY-02 |
| AC-10 | Shopper requests deletion while generation is running | Cancel/block delivery; purge tracked to completion or visible failure; late worker/webhook cannot restore content | TRY-05, TRUST-01 |
| AC-11 | Quality gate fails after one retry or provider policy rejects a photo | No misleading preview; neutral error/retake or exit; no third automatic attempt | TRY-03, TRY-04, OPS-01 |
| AC-12 | Same Shopify test webhook arrives repeatedly; another event contains conflicting creator evidence | Count once; label test; ambiguous attribution remains explicit under deterministic precedence | TRACK-01, TRACK-02 |
| AC-13 | Dashboard has no live orders but contains seeded fixture events | Live orders show zero or unavailable as appropriate; fixture data is separately labeled, with no fabricated growth/ROI | CAMP-02, TRACK-03 |
| AC-14 | Keyboard/mobile user opens a finding and returns from the evidence player | Focus is preserved, timestamp and evidence are readable, controls are reachable, status is not color-only | ACCESS-01 |
| AC-15 | Workspace spend cap is reached or a duplicate job is retried | No duplicate paid work; bounded retry/cap state with safe next action and traceable job status | OPS-01 |
| AC-16 | Rule source changes after a historical review | Old pack/approval remains reproducible; current review requires the intended new version; rule publication requires an authorized human | CAMP-01, CHECK-03, CHECK-08 |
| AC-17 | An India or unknown-eligibility operator/end user attempts a Muse Image preview | Block before photo upload/provider call; show restricted/unknown eligibility reason; no silent alternate provider or geography bypass | MODEL-02, TRY-01 |
| AC-18 | Wonder generates a dossier with an invented citation, stale snapshot or inaccessible record ID | Reject/flag unsupported statements; never present them as observed facts; no state-changing action; core review remains available | WONDER-01, FOUND-01 |
| AC-19 | Uploaded caption/transcript asks the model to ignore rules, reveal another campaign or send a message | Treat it as untrusted content to assess, not executable instructions; no unauthorized retrieval or external action | FOUND-01, CHECK-03, WONDER-01 |

Requirement references in this table omit the common `VCH-` prefix for readability.

## 8. Evidence of product value

The first demo must prove one authorized draft → evidence-backed assessment → fix request → revised version → explicit reviewer decision cycle. At least one failure path and one no-issues result must be demonstrated honestly. Show the exact dataset, supported modalities/languages, model/prompt/rule versions and execution provenance alongside any measured quality result.

Proposed Check evaluation starts with a small rights-cleared labeled corpus containing clean content, missing/late disclosure, spoken claims, on-screen text and intentionally unavailable modalities. English is the baseline; Hindi–English code-switching is an extension only after access and evaluation establish support. Keep a held-out set separate from prompt development and include clean negatives and uncertain cases. Source B251 proposes ≥85% recall and <20% incorrect findings; these are **source-stated aspirational targets**, not observed performance, legal release thresholds, or sufficient evidence for broad customer claims. Pilot gates belong to the [quality plan](../engineering/quality-and-operations.md).

For Try, score identity preservation, product shape/color/logo fidelity, artifacts, safety, latency and failure behavior across consented examples. Product detection by a segmenter alone is not fidelity validation. The source's 70% acceptability threshold is a demo hypothesis; a real pilot needs an explicit per-SKU gate and enough independent human assessment to justify exposing the experience. If the gate fails, keep Try disabled or show separately labeled prerecorded, consented examples without claiming live capability.

For business validation, record interviews with marketing users and reviewers, baseline minutes per review, revision rounds, time to human decision, reviewer weekly reuse and stated willingness to pay. Treat conversions and testimonials as observations only when actually collected with permission. Source pricing, margins, market figures, acquisition goals and return-rate claims remain hypotheses; no subscription billing or investor promise follows from them.

## 9. Bounded extensions after a validated pilot

1. **Review reliability:** stronger version comparison, reviewed sector packs, audit export and controlled reviewer feedback/evaluations. This improves the core wedge before adding new customer segments.
2. **Campaign evidence:** authorized catalog/order integration and richer curated discovery, maintaining precise attribution and data-rights provenance.
3. **Meaningful model/channel expansion:** add the cited Wonder dossier, enable geographically eligible and proven eyewear Try SKUs, then an approved messaging channel; expand categories only after measured fidelity and privacy review. Keep India policy restrictions visible while expanding eligible international experiences.

Each extension needs a user problem, access/rights check, acceptance scenarios and measured operating cost. Do not add autonomous agents, retrieval infrastructure, broad social scraping, cross-brand profiling or enterprise features merely because they appeared in the original long-term vision.

## 10. Founder decisions still needed

| Decision | Proposed default | Consequence if changed |
| --- | --- | --- |
| Initial pilot buyer and primary module | Small D2C eyewear brand/agency; Check first | A Try-first business needs earlier fidelity and channel-access gates; regulated buyers need specialist rules and support |
| First supported rule pack/language within confirmed India + international markets | One explicitly scoped, reviewed India/brand pack; English first; additional eligible markets gated | Additional jurisdiction/language increases evaluation and legal-review scope; international availability is not global legal coverage |
| Mandatory demo experience | Check/revision/human decision; curated Find and test Track | Making live WhatsApp Try mandatory places the critical path on independent channel access and generation quality |
| Review owner | Named human reviewer with explicit membership | No real pilot if no accountable reviewer exists |
| Rights-cleared pilot assets | Invited creator uploads and consented team material | Broader discovery requires official/authorized/licensed access and separate validation |

These choices should be recorded in [architecture decisions](../architecture/decisions.md) and the
[roadmap](../engineering/roadmap.md) before the corresponding deferred capability is implemented or
activated. No account connection, paid call, publication, outreach or deployment is authorized or
performed by writing these requirements.
