# Vouch experience and design specification

Status: **workspace, Check review, curated Find, India Try gating and initial creator draft UI are implemented; broader experience remains proposed and
founder validation is required.** Component checks, production build and desktop/mobile browser
workflow verification pass for the fixture slice on Supabase Postgres. Finding decisions can reopen
review and invalidate prior approval; revisions start unchecked. Updated 2026-10-28; see
[implementation status](../engineering/implementation-status.md).

2026-10-26 visual refinement: [Vouch Signal](../../design.md) is the canonical visual system. It
retains the implemented workflow while replacing the earlier graphite/lime treatment with a
cool-neutral editorial canvas, Vouch red and evidence blue across the workspace, campaign review,
sign-in and creator portal. Preserve existing routes, role/notice/version guards and truthful
fixture labels. The dashboard may compose only real returned data; Find uses only tenant-curated
evidence, Try exposes its India policy restriction before upload, and Track remains visibly
deferred rather than becoming a simulated product surface. Visual/browser proof is recorded
separately from workflow verification in the execution ledger.

### Implemented authenticated experience

Local Supabase mode replaces the fixture identity selector with password sign-in, active workspace
selection and sign-out. Wrong credentials clear the password and show a safe error; session/role
failures remove private views. A signed-in user without active membership gets an explicit empty
state, not an automatic admin workspace. Account provisioning and password recovery remain manual.
The fixture-provider banner remains visible: real authentication does not imply live AI analysis.

Accepted 2026-10-24 [extension](../architecture/oauth-storage-motion.md): show a Google sign-in
button, disabled with an explanation until provider setup; retain password login. A verified
Google identity without an assigned workspace receives the same no-access state as any other
unprovisioned identity. The workspace storage panel separates stored originals, upload reservations
and pending cleanup; unavailable data never appears as zero. Oversized files receive an immediate
explanation that preserves the caption and selected file. Original quality is retained, not silently
re-encoded. Scroll-responsive 3D, a subtle border beam and loading orbs follow the Signal motion
contract, reduced-motion preferences and actual pending state; they do not imply live AI activity.

The uploader renders the full current local draft processing notice before intake, its immutable
version/hash provenance and a public JSON link. Rights attestation and notice acknowledgment are
separate required controls. Loading/failure/unknown notice blocks upload and offers retry. A stale
notice error reloads the notice, clears its acknowledgment and preserves the other draft fields.
Selected versions show their actual receipt or explicit legacy/missing authorization, never an
inferred acceptance. Admin/marketer withdrawal requires a deliberate confirmation and displays the
same truthful cleanup receipt/history used by deletion. Review controls use the checked version's
authorization, not merely a newer upload's receipt. See the execution ledger for current proof.

Media mode is disclosed separately. Fixture media is signature-only with a synthetic ten-second
timebase; decoded mode measures/validates the actual file but its Check results remain explicitly
synthetic. Unknown mode blocks upload. Decode failure preserves file/caption/rights state and never
offers a fixture fallback. Selected versions show measured/synthetic duration, dimensions, audio,
processor/hash and identity time mapping only when a real processing snapshot exists. Legacy
metadata is not invented. Both decoded desktop/mobile uploads and deletion were browser-verified;
see the execution ledger for the exact code-stage proof.

The creation drawer uses native user-controlled disclosure and waits for required catalog options;
late list/session fetches must not close an edited form. Empty queued/partial findings are not
labeled a clean result. Deletion shows the actual receipt/destinations, incomplete cleanup and a
retry action. Supabase sign-in widths 320/768/1024/1440 and keyboard input order are browser-tested;
the campaign's durable deletion history also recovers after reload. It shows member/system
attribution, destination states, retry timing and exhausted automatic attempts. Only admin/marketer
users see manual cleanup retry. A failed receipt never uses success styling; refresh is explicit
so an old displayed receipt does not imply a new confirmed Storage check.
real local sign-in through revision/approval is checked on desktop and mobile.

This specification translates the supplied Find/Check/Try/Track vision into buildable journeys. [Requirements](../product/requirements.md) define scope and acceptance; [architecture](../architecture/overview.md) and [API contracts](../architecture/api-contracts.md) define system behavior. Source references use B-numbers from the [extracted DOCX](../source/design-document-extracted.md). Source-stated ideas are inputs, not verified API capabilities, law, or instructions to execute.

## 1. Experience principles

- **Evidence before reassurance.** Every substantive Check finding opens the relevant moment and rule source. A green badge never substitutes for evidence or a named human review.
- **One campaign, four jobs.** Preserve Find, Check, Try and Track as a coherent journey; make unavailable or conditional modules explicit. Prioritize the next useful action over an ornamental analytics dashboard.
- **Show what ran.** Fixture, cached, live, unavailable, partial and stale states are visible where a user makes a decision. Cached output retains its original run timestamp and versions.
- **Preserve versions.** The UI always names the content/caption version under review. Revised media never inherits the appearance of an earlier approval.
- **Small, explainable actions.** Generating a message creates a draft; sending and approving are distinct human actions. Product language says “potential issue,” “review,” and “AI preview.”

The founder confirmed India plus international markets and purposeful coverage of the Meta model families. The interface preserves one four-module product while exposing capability differences by region. Check-first sequencing and the detailed interface below remain proposed. Region restrictions are not treated as a transient missing-key error.

Canonical invocation modes are `fixture`, `recorded` and `live`. Cache freshness, analysis completeness and provider capability are separate attributes. An original live result retrieved from cache must not appear to be a newly completed live run; a recorded artifact must show its original authorization and execution provenance.

## 2. Accepted brand system

The executable [tokens](../../tokens.css) use cool canvas `#F5F7FA`, white surfaces, primary ink
`#151922`, muted copy `#687386`, Vouch red `#930500` and evidence blue `#95BBEA`. Red identifies
the brand, primary actions and consequential decisions; blue supports evidence and capability
context. Status still includes text and may use semantic green, amber or red only for the state it
actually represents. The source tagline “Everything stays compliant” remains an unacceptable
guarantee; the product direction is **“Creator campaigns you can trust.”** Trademark/name checks
remain open.

Editorial headings use the local system serif stack. Space Grotesk carries UI headings and metrics;
IBM Plex Sans carries body, navigation and forms; IBM Plex Mono is reserved for hashes, IDs and
timecodes. These UI families are self-hosted. White is the dominant surface, borders stay cool and
shadows are reserved for hierarchy rather than applied to every block. Purpose-specific evidence,
authorization, approval, storage and campaign surfaces must remain distinguishable without relying
on color alone.

Validate actual backgrounds, focus rings, disabled states, video overlays and responsive layouts
during implementation. Aim for WCAG 2.2 AA across the core journeys: at least 4.5:1 for normal text
and 3:1 for relevant non-text controls. The visual tone is confident and practical: plain language,
useful density, visible provenance and room for video evidence. Avoid “100% safe,” compliance
shields, fake live counters, animated revenue numbers or unverified customer logos. Motion is
limited to helpful transitions and respects reduced-motion preferences.

## 3. Information architecture

| Area | Purpose and primary action |
| --- | --- |
| Home | “What needs attention”: drafts awaiting review, failed jobs and incomplete setup; open a real task |
| Campaigns | Create/select campaign; see product, roster, pinned rules and current review activity |
| Campaign → Overview | Campaign context and actual next steps; identify current demo/live environment; optional cited evidence dossier |
| Campaign → Find | Curated creator evidence, source/rights status, shortlist and copyable outreach draft |
| Campaign → Check | Submissions and version history; open the evidence review workspace |
| Campaign → Try | Conditional SKU readiness, quality gate and consent/delivery readiness; disable until eligible |
| Campaign → Track | Defined funnel events and deterministic attribution; separate fixture/test/live data |
| Rule packs | Current/archived versions, provenance and draft/reviewed status; authorized edit/publish workflow later |
| Settings | Team/roles, provider connection status, usage caps, retention/deletion, audit access |
| Creator submission | Separate narrow route for scoped invitation, initial upload/receipt/draft publication, explicit allowlisted feedback and exact status; later revision and withdrawal remain planned |
| Shopper Try | Separate mobile route/approved messaging flow; no brand-admin navigation |

Implemented desktop shell: a persistent navigation rail with workspace/campaign context, compact
workspace bar and a main content region. Keep campaign switching explicit so a reviewer cannot
accidentally approve another brand's content. On small screens, the rail becomes a compact brand
row with Home/Campaigns navigation while the page heading preserves campaign/version context.
Avoid horizontal page scrolling.

Conditional modules show the actual gating reason: “Awaiting model access,” “Quality review required,” or “Not available in this region.” They should not resemble working features behind an unexplained paywall. Pricing/upgrade UI is outside the first demo.

## 4. Brand onboarding and campaign setup

Proposed steps: create/select workspace → identify roles → create campaign → add product/reference assets → choose the supported market and pinned rule pack → invite/upload a creator draft. Integrations are optional setup branches while the first demo supports rights-cleared local inputs. Do not present a pasted Shopify URL as a successful catalog connection.

Each connection card shows one of: not connected, connecting, connected to a named account, permission limited, expired/revoked, or failed. “Installed” or “configured” is not connected/authenticated. The connected account and environment must be visible before an account-affecting action. Missing model APIs should display “Unavailable — awaiting provider access” rather than asking users to enter imaginary keys or showing a green connection state.

Campaign setup explains that selected rule packs are versioned. Draft/demo packs carry a persistent “Not legally reviewed” label. A custom brand-policy rule must be labeled a brand requirement, not a statutory obligation. Changing a pack for future checks opens a version-change explanation and does not rewrite historical review records.

First-run empty states should guide one action: “Upload a draft to start review.” A separate, explicit “Explore sample campaign” choice opens labeled fixture data. Never seed customer workspaces with plausible-looking live sales.

## 5. Check: primary reviewer journey

### Submission and queue

The submission form identifies campaign/creator, content rights attestation, video, caption, expected language and applicable pack version. Show supported limits from the actual configured contract, not guessed provider limits. Validate before upload where possible and server-side in all cases. Announce errors beside fields, preserve the caption after failure, and show a resumable/retry action only when supported.

After submission, show the asset version, upload receipt, job status and stages such as “Preparing media,” “Reading speech,” “Inspecting visuals,” and “Evaluating rules.” Stage labels reflect actual work; no simulated percentage or fabricated countdown. Users can leave and return. A job ID supports safe retry/status recovery without a duplicate paid job.

### Review workspace

At the top, show the campaign, creator, content version, caption version, execution provenance, run time, pinned pack and evidence coverage. Place **AI assessment** and **Human review** in separate labeled regions. Example: “AI assessment: Fixes suggested” alongside “Human review: Not reviewed.” A no-issues AI result must not make the whole page look approved.

Before the workflow controls, show a compact **What needs attention now** brief derived from current
campaign records. Separate blocking issues from next actions, link each item to the exact review
region and state that the summary is record-derived. Loading or failure must not render a false
ready state. Wonder may later add a bounded cited dossier, but is not required for this core brief.

The content specification panel lists approved product wording beside its evidence label and expiry
state, then shows each campaign requirement as **Observed**, **Missing** or **Unknown** for the
current version. Exact caption matches must say they are exact matches. Visual fixture evidence may
support human review but must not claim exact SKU identity. Only admins and marketers author these
inputs; all members may inspect their provenance and limitations.

Proposed desktop layout: video/player and transcript on one side; findings/rule detail on the other; a narrow timeline beneath the player. On mobile, stack player, summaries, finding list and detail with clear return/focus behavior. Keep destructive or approval actions out of accidental playback tap areas.

Each finding shows:

- Plain issue title and severity text/icon, distinct from uncertainty.
- Timestamp **range**, modality and exact quote/visual description, linked to the player or caption location.
- Rule ID, pack version, applicability and a link to the cited source; draft/brand-policy labels stay visible.
- Evidence uncertainty and coverage limitations in words. Raw model confidence, if retained for debugging, is not a “98% compliant” score.
- Suggested next action, with “Accept finding,” “Dismiss with reason,” and “Needs review/incorrect” controls available only to an authorized reviewer.

Timecodes use `mm:ss` or `hh:mm:ss` plus a range where needed. Transcript turn ranges must not masquerade as word-level alignment. Frame sampling creates timing uncertainty that should be disclosed in evidence detail; a sampled absence cannot prove that an object never appeared. Caption findings are labeled caption evidence instead of pretending to have a video timestamp.

The player must provide keyboard playback/seeking, readable captions/transcript where available, no autoplay with sound, and a clear selected-finding state. Opening a timestamp moves playback without losing keyboard focus. Text summaries and source images must remain available when a video cannot load; such a failure may block approval if evidence cannot be reviewed.

### Fix request and revision

“Prepare fix request” opens a reviewable message containing finding references, timestamps and suggested edits. Default action is “Copy message” in the demo. A later Send action must show recipient/channel and delivery result. Opening or generating a draft never sends it.

A creator revision is a new asset/caption version with a new review context. Comparison labels are **Added**, **Still detected**, **No longer detected** and **Cannot compare**. Use “Resolved” only after the available evidence and reviewer decision support that claim. State changed rule/model/prompt versions and modality coverage before comparing counts; fewer findings alone is not proof of improvement.

### Human decision

The approval dialog names the content/caption version, current analysis and pinned pack, summarizes outstanding finding decisions and states: “This records your review decision for this version. Vouch does not certify legal compliance or publish the content.” Require a deliberate confirm action by an authorized reviewer; never preselect approval.

Disable approval with a specific reason for incomplete/partial analysis, missing required evidence, unresolved required blockers, stale context, insufficient role or superseded content. Do not offer an inconspicuous “approve anyway” path. A rejected finding may be dismissed by a reviewer with a rationale; this records the human disagreement without rewriting the original observation.

After approval, show the reviewer name/time and exact approved version. Any subsequent revision prominently says “New version — review required.” Historical approvals remain in a version history with revocation/supersession events; they must not supply a misleading green badge on the current version. Publishing to a social channel is outside this flow.

While the exact version remains approved, offer a secondary “Download approval report” action.
The downloaded report names the immutable hashes and pinned check provenance, lists reviewed
evidence and finding decisions, and leads with the non-certificate limitation. Do not leave a stale
download action visible after revocation or supersession.

## 6. Creator guest experience

The isolated `/creator` landing, fragment exchange, cookie-session resume, allowlisted submission
view, guest-attributed upload/finalize, applicable immutable notice/receipt, initial draft
publication and explicitly shared feedback are implemented locally. Follow the [scoped portal architecture](../architecture/creator-portal.md)
for later revision and withdrawal work; member screens are not
exposed through invitation tokens.

An invitation landing page names the brand, campaign, requested submission, expiry and why the link grants access. The token must be scoped and revocable; “no login” never means unrestricted access. Do not expose other creators, private reviewer discussions, usage cost or shopper information.

Implemented journey: invitation → limited privacy/rights notice → upload draft and caption → submitted receipt/initial version → explicitly permitted timestamped feedback with fixture/live provenance and current/historical labeling. Remaining journey: upload revision → scoped withdrawal. The portal uses safe active/expired/unavailable states and exact-version approval text; later mutation states must retain those boundaries. Keep the accessible mobile uploader and use a fresh-link request path without disclosing workspace membership.

For upload interruption, retain non-sensitive form state when safe and offer retry; do not promise resume support if absent. For an expired invite, show how to contact the brand; never silently replace it with a broadly scoped session. Approval and decline remain brand decisions, not creator self-service controls.

## 7. Find: curated evidence, not a social search claim

The implemented `/find` route lists tenant-owned creators with a visible “Curated collection” label, source/permission/verification/capture provenance and filters. Each card distinguishes category relevance from an exact product match and shows whether the proof was human-curated, model-analyzed or cached. Adding a creator requires explicit compatible evidence and persists that write-once evidence link. Outreach is an editable local draft and never sends. There is no claim of verified audience demographics or fraud scoring without an authorized source.

Select a creator to inspect the timestamped proof, usage rights/source and campaign history permitted within the workspace. “Add to campaign” changes the roster; “Draft outreach” creates a reviewable draft. The empty result state says “No candidates in this collection match your filters,” not “No creators exist.” Broad platform search is shown only when an actual verified connector is implemented.

### On-demand campaign evidence dossier

Within the campaign overview or Check summary, an optional “Prepare evidence dossier” action invokes Wonder for a meaningful read-only synthesis of authorized stored evidence. Before invocation, show the selected campaign, time range, included checks/events and budget impact where known. Do not call it automatically on every dashboard load.

The dossier separates **Observed facts** from **Recommendations for your team**. Each factual claim links to a permitted finding, review or event record and its snapshot/version. Show the generating family/model, time, execution provenance and “AI draft — verify sources before use.” Unsupported citations are flagged/rejected, and a source record removed or superseded after generation marks the draft stale.

The panel cannot approve content, change rules, contact creators or publish/export externally without a separate authorized human action. An embedded caption or transcript cannot instruct it to fetch other tenants or execute tools. If Wonder is unavailable or generation fails, keep the evidence list and normal campaign workflow available; do not create a report that implies a live Wonder run. This is an added capability within the existing modules, not a fifth product module.

## 8. Try: conditional, mobile-first experience

Try is conditional until [API readiness](../integrations/meta-api-readiness.md), geographic eligibility, per-SKU fidelity, provider privacy, and delivery gates pass. Meta's [Geographic Use Policy](https://dev.meta.ai/legal/geographic-use-policy), section 2.2, restricts Muse Image access from India and availability to India end users. The implemented `/try` route shows the India policy decision before any photo control, makes catalog visibility distinct from permission, and offers safe Find/Check paths. Gate deployment, operator and end-user eligibility and fail closed when eligibility is unknown; do not suggest location workarounds. The same consent and safety requirements apply to a mobile web fallback and a future WhatsApp flow; a different channel cannot bypass a model restriction. Model access alone is not proof of messaging access.

An alternate provider remains an unselected adapter possibility until its policy/privacy, quality, consent and hackathon acceptance are verified. Never automatically fail over personal photos, attribute an alternate preview to Muse Image, or present a fixture as live. Eligible international users may receive a different feature set from India users while remaining in the same campaign product.

Proposed shopper sequence:

1. A creator link/QR opens a named brand/product with the correct campaign reference.
2. Show a short notice before photo upload: purpose, provider processing, retention/deletion, preview limits and how to leave. Link the full privacy notice. Ask explicit consent, adult self-attestation and confirmation that the shopper may use the photo.
3. Offer product selection and photo guidance; request one clear, front-facing, well-lit photo of the shopper. Do not upload automatically when the consent page loads.
4. Check input suitability; give neutral retake advice for an unsuitable or ambiguous photo. Adult self-attestation is not verified age, and a model estimate must never be described as proof.
5. Show honest queued/processing state with cancel/exit. Avoid an unsupported “20 seconds guaranteed” promise; observed timing may be shown after measurement.
6. After safety and quality gates, show the source product and a visibly labeled AI preview. Display “Fit, size and exact appearance are not guaranteed,” the real product reference/price source when known, and a clearly identified destination for Buy.
7. Allow a bounded new attempt or product choice, user-initiated share/download and immediate deletion request. Keep the AI label on exported images.

Consent copy is a draft requiring privacy/legal validation. Do not include a “no training” guarantee until provider settings and terms substantiate it. Proposed first-party retention is no more than 24 hours from receipt, with earlier deletion on request; show a deletion due time and distinguish provider retention limits where applicable.

| State | Shopper sees | Required behavior |
| --- | --- | --- |
| Consent declined/adulthood not confirmed | “You can browse the product without sending a photo.” | No photo collection or generation |
| Policy-restricted region | “AI previews are not available in your region. You can still view this product.” | Block restricted Image processing before photo collection; no geography bypass |
| Eligibility unknown | “We can't confirm whether this preview is available for your session.” | Resolve eligibility or exit without photo collection; no default allow |
| Photo unsuitable | “Please use a clear photo with only you in the frame.” | Retake or exit; no sensitive age/body diagnosis |
| Queued/processing | Honest stage and cancel control | No fake countdown; duplicate message/upload does not duplicate generation |
| Preview passed | Labeled AI preview, original product, limitations and Buy | Share is explicit; no claim of exact fit or identity transformation |
| Safety rejected/quality failed | Neutral explanation and allowed retake/exit | Do not reveal unsafe image; at most one automatic generation retry |
| Provider/rate-limit timeout | “We couldn't prepare a preview. Try later or view the product.” | No fabricated result; no indefinite spinner or retry loop |
| Session expired/revoked | “This session has ended. Start again to give consent.” | No new upload or delivery from the expired session |
| Deletion requested | “Deletion requested — processing stopped.” | Block late delivery, cancel jobs and show pending/completed/failure accurately |
| Deleted | “Your Vouch photos and previews were deleted.” with precise scope | Do not claim third-party copies were deleted without confirmation |

Changing the product after a preview must not indefinitely extend photo retention. If a valid source photo no longer exists, request a new consented submission. Messaging-specific service-window/template restrictions and recipient limits require current verification before launch; do not silently move shoppers to unconsented outbound messages.

## 9. Track: useful numbers with visible definitions

Use a small funnel: eligible sessions → previews delivered → buy-link clicks → attributed test/live orders. Every chart names its time range, data source, environment and freshness. A tooltip or definitions panel explains each event and denominator. A failed preview is not delivered; a click is not a purchase.

Keep fixture/sample, sandbox/test and live production series visually and logically separate. Use a persistent “Sample data” banner on fixture screens and “Test order” on sandbox orders. Empty live metrics show zero only when collection is working and the observed count is actually zero; disconnected/incomplete collection shows unavailable. Never animate placeholder revenue into a live-looking card.

Creator rows link to supporting events, attribution rule and conflict/unassigned state. Refunds/cancellations are represented according to the deterministic policy; do not let a summarizing model assign credit. No “incremental revenue,” “conversion lift,” or “compliance score” claim is derived from a small attributed-order list. Source B95's combined leaderboard is deferred until its fairness, denominators and interpretation can be validated.

## 10. Common system states and accessibility

| State | Display contract |
| --- | --- |
| Loading | Accessible status message or skeleton; preserve known context and avoid fabricated data |
| Empty | State whether no records exist or filters exclude them; offer one relevant next action |
| Partial/missing evidence | Name the unavailable stage/modality and its consequence; do not use a pass-colored summary |
| Cached | Original execution time, source versions and “Cached result”; distinguish from a newly completed call |
| Fixture/demo | Persistent page banner plus local result badges and exported report metadata |
| Error | Plain description, safe next action and optional support/job reference; no raw stack traces, secrets or signed URLs |
| Stale/superseded | Identify the newer version/context and link to it; historical decisions remain readable |
| Permission denied | No leaked object details; explain needed role only where membership permits |
| Policy restricted | Explain capability unavailable in this region, distinct from awaiting credentials; retain other eligible modules |
| Offline/interrupted | Preserve safe work state and show whether an action actually reached the server |
| Destructive/privacy action | Name exact scope and consequence; avoid an inaccurate “deleted” success before purge completion |

All primary actions have accessible names, visible keyboard focus and an order matching the visual flow. Dialogs trap/restore focus appropriately; errors are connected to fields; job updates use polite live announcements without repeatedly stealing focus. Status includes text and a distinguishing icon/shape. Prefer 44px touch targets and adequate spacing; do not make the timeline the only way to reach a finding.

Check the brand workspace at desktop and 320–375px mobile widths, text zoom, keyboard-only navigation and reduced motion. Include long creator names, long/Unicode captions, mixed Hindi/English text, missing images, many findings and slow media. Provide textual evidence when visual playback is inaccessible; do not show an approval path that assumes the reviewer inspected evidence they could not load.

## 11. Design acceptance and next artifacts

Before implementing the remaining proposed screens, validate their scope with the founder and
sketch the revision comparison, reviewer dialog, creator mobile upload and conditional Try
consent/failure screen. Wireframes/prototypes must carry the same fixture/provenance labels as the
final product.

Before a demo/pilot, inspect the actual rendered core journey, including one interrupted upload, a partial model run, a new version after approval, an expired guest link, and a deletion request during a Try job if enabled. Review screenshots with real fixture labels and no unsupported live metrics. Check keyboard focus, meaningful contrast, responsive evidence playback and confirmation copy in the browser; compilation is not a design acceptance test.

Open choices: pilot validation of the accepted Check-led Signal workbench; first supported legal packs/languages within the confirmed India plus international market direction; final creator invitation policy; legally reviewed consent/privacy wording; whether messaging and commerce connectors are actually available; and pilot-specific retention. Record decisions in [decisions](../architecture/decisions.md) rather than letting interface copy establish an unapproved policy.
