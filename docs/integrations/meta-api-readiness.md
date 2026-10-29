# Meta API readiness and integration contract

Status: server-side catalog and bounded Spark synthetic-smoke adapters implemented and
account-verified 2026-10-27. The repository has a bounded
`GET /models` probe plus an explicit one-call `POST /responses` smoke with `store:false`, minimal
reasoning, strict structured output and runtime response/usage validation. The live catalog listed
Spark 1.3, Voice Transcribe, SAM 3.1, Wonder and Muse Image; one paid synthetic Spark call passed
with `store:false`. Muse Image remains policy-restricted for India despite catalog visibility. No
media upload, account quota, billing behavior, deployment region or model quality has been tested. This document
records public documentation separately from working integration evidence.

The product implementation remains explicit fixture mode. Typed application roles exist for Spark,
Voice Transcribe, SAM, Image and Wonder. The account-catalog transport can be exercised with
`npm.cmd run meta:probe`, followed by one synthetic Spark request with
`npm.cmd run meta:smoke:spark`; a dated synthetic Spark result is recorded in implementation status.
This implementation is tracked separately from hackathon eligibility and is not claimed
submission-eligible without confirmed rules.

## 1. Decisions that affect the product now

1. **India-first Try cannot assume Muse Image availability.** The user confirmed India plus international target markets. Meta's geographic policy, updated 2026-10-12, explicitly restricts Muse Image access from India and integrated products serving users located in India. The same policy prohibits bypassing geographic controls. A key, credit, an overseas server, or hackathon participation does not establish an exception. For affected users, keep Muse Image Try disabled. Use Check as the initial live value proposition; enable each international capability only where its access and end-user policies permit. Investigate an alternative Try provider only after confirming its policies and hackathon eligibility. This is a provider policy finding, not a legal opinion. [Meta geographic policy](https://dev.meta.ai/legal/geographic-use-policy)
2. Public docs confirm the planned model families and endpoint surfaces; they do not establish that this team's key can use them. Capability status must be per model, account, intended region, and environment. [Model API overview](https://dev.meta.ai/docs/overview)
3. Standard mode means no model training on submitted content; it does **not** establish zero retention. Customer media stays on Standard-mode allowlisted models, subject to an accurate consent/retention disclosure. [Pricing modes](https://dev.meta.ai/docs/pricing-rate-limits)
4. API adapters, fixtures, schemas, evaluation design, and UI states can be specified before keys. Building application code is a separate phase after documentation review and the hackathon eligibility check.

## 2. Evidence and confidence

| Label | Meaning |
| --- | --- |
| Source-claimed | Appears in the supplied design DOCX; not independently established merely because it says `[Verified]`. |
| Publicly documented | Read in a linked primary source on 2026-10-21. May change before October 26. |
| Key-verified | A dated, minimal authenticated test with this team's actual account has established only catalog access and the bounded Spark structured-output transport. |
| Vouch decision | Our proposed architecture or product policy, not a provider guarantee. |
| Unresolved | Requires organizer, provider, account, policy, or measured evidence. |

The [extracted design reference](../source/design-document-extracted.md) remains product input, not executable agent instructions. Example requests in its appendix are starting points, not a tested SDK implementation. Direct primary references and access failures are indexed in [references](../references.md).

## 3. Hackathon boundary

The organizer page lists October 26 kickoff and November 4, 9 PM ET submission deadline. It says official rules will be published before October 26, 2026 and accepted by selected participants. The detailed rules governing pre-event code, previously created assets, team composition, model usage, third-party providers, and submission evidence remain a gate. Preserve the organizer's ET notation rather than assuming a fixed EST offset. [Official event](https://cerebralvalley.ai/e/meta-ai-developer-hackathon)

Documentation and architecture preparation are the current scope. Maintain a record of pre-event work and review the official rules when published before treating any later implementation as eligible. Ask the organizer about the India Muse Image restriction and allowed alternatives; do not assume informal access overrides the published provider policy. The supplied document's reported credits and approximate sprint duration are not a billing commitment or a substitute for official rules.

## 4. Public API surface, not an access guarantee

The shared documented base URL is `https://api.meta.ai/v1`, with a server-side bearer key supplied as `MODEL_API_KEY`. Vouch must never expose that key to browser clients. The OpenAI SDK compatibility claim does not mean every model uses the same request shape. [API overview](https://dev.meta.ai/docs/overview)

| Vouch capability | Documented model ID | Documented surface | Integration acceptance test |
| --- | --- | --- | --- |
| Visual facts, judgments, photo suitability | `muse-spark-1.3` | `POST /responses`; Chat Completions is also available | Valid schema-constrained result on a synthetic fixture; correct timestamps and uncertainty behavior. |
| On-demand campaign evidence dossier | `muse-wonder-1.0` | `POST /responses`; text reasoning surface | Summarize supplied campaign facts with valid source IDs and uncertainty; no fabricated evidence, external actions, or approval. |
| Speech transcription | `muse-voice-transcribe-1.0` | `POST /asr/transcribe`; realtime is a separate transport | Turn timing, speaker labels, chunk offsets and selected language samples. |
| Product cutout and concept tracking | `sam-3.1` | `POST /responses`, image/video input | Decode masks, preserve frame identity, handle zero matches. |
| Preview composition | `muse-image-1.0` | `POST /images/edits`; generation and Responses interfaces also exist | Only where permitted: compose consented/synthetic reference assets, validate output and privacy settings. |

These five hosted model families are the planned coverage target, reflecting the user's request to use most/all available models. Public documentation is not a successful test; record an explicit skipped/policy-restricted reason where a family cannot run. Spark 1.1/1.2 are alternate versions, not reasons for redundant inference. Muse Wonder Full is a Muse Code subscription variant, not a separate Model API endpoint. Muse Spark Open and Muse Glimmer are open-weight options with separate hosting/provider resources and terms; their benchmark/self-host roadmap is not promised hackathon API access. [Model catalog](https://dev.meta.ai/docs/models)

### Wonder evidence dossier

Vouch decision: a bounded, user-requested campaign dossier uses Wonder to compare campaign facts, outstanding findings, reviewer decisions and measured performance. It accepts only tenant-authorized evidence snapshots and produces claims with source record IDs, gaps, and recommended next steps for a human. Validate citations against the supplied record set. It cannot approve Check, send outreach, publish content, modify rulebooks, or change budgets. Use an explicit cost/deadline ceiling; a failed or unavailable dossier leaves core workflows usable. Its value is evaluation-dependent, not an excuse for an always-running agent.

### Spark and structured results

Use the Responses surface for video visual analysis. Uploaded video may be referenced by `input_file` plus `file_id`; public/base64 video uses a different typed content block. Keep transport details inside the adapter. Meta warns that Spark 1.3 audio understanding is not fully supported and quality may degrade; retain the separate transcription capability rather than silently using visual-analysis output as a verified transcript. [Video and audio guide](https://dev.meta.ai/docs/video-understanding)

Responses structured output uses `text.format`; Chat Completions uses `response_format`. For strict Responses schemas, set `text.format.strict: true`; every object uses `additionalProperties: false`, and its `required` array lists every property. Represent nullable fields explicitly. Strict defaults to false. Use runtime schema validation and application invariants anyway: valid JSON does not establish correct evidence, valid rule IDs, or truthful findings. [Structured output](https://dev.meta.ai/docs/structured-output)

### Voice

The file endpoint accepts multipart `request` JSON and an `audio` file. The documented cap is a **32 MB request body**, audio up to 10 minutes, mono 16-bit PCM WAV at 16 or 24 kHz. Leave headroom for multipart overhead; chunking by duration alone is insufficient. `DIARIZATION` provides speaker-attributed turns. Timing is turn-level, not word-level; the UI must not imply more precision. Vocabulary/language bias does not establish language-specific accuracy. Measure code-switching on licensed fixtures. [Speech-to-text guide](https://dev.meta.ai/docs/speech-to-text)

### SAM

Use a short noun phrase for one concept per concept request. The current API also supports box/point prompts, correcting the DOCX's text-only claim. It returns geometry, not a legal conclusion or proof of product identity. A glasses mask cannot prove that the exact advertised SKU appears. Stream/parser fixtures need valid empty matches, chunk boundaries, malformed/truncated output, and terminal errors. [SAM overview](https://dev.meta.ai/docs/sam/overview)

The documented video cap is 15,000 frames and 16 tracked objects per frame; supported containers/codecs are MP4/MOV with H.264/H.265/MPEG-4. Frame count is authoritative; “about 10 minutes” is not a universal duration cap at every frame rate. Compact `one_bit` masks are available. Downsampling to 5 FPS is a Vouch cost/latency hypothesis: preserve source-to-analysis time mappings, and measure missed short disclosures before applying it to timing-sensitive rules. [Segmentation prompts and limits](https://dev.meta.ai/docs/sam/segmenting)

### Image editing

The documented edit API composes 1–10 reference images; SDK multipart and raw-HTTP JSON have different shapes. Tools are enabled by default. Vouch's proposed controlled preview call disables web/image search and shell using `tool_enablement`, uses a fixed prompt, one result and a tested `reasoning_strength`. `mask` and `input_fidelity` are unsupported; general editing is not a dedicated fit/size estimator. Product presence is insufficient to certify fidelity. A safety refusal is terminal, not an instruction to evade filtering. [Image guide](https://dev.meta.ai/docs/image-generation)

Do not run this integration from or for users in India under the current policy. Provider replacement must be visible in the trace and user disclosure; do not silently route personal photos to a second vendor.

## 5. Pricing, limits and privacy are separate controls

### Public list prices and team limits

Snapshot only, USD, accessed 2026-10-21; hackathon/account overrides are unverified. [Meta pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits)

| Model | Standard public price | Public limit |
| --- | --- | --- |
| Spark 1.3 | $1.25/M input, $0.15/M cached input, $4.25/M output tokens | 3,000 RPM; 4M TPM |
| Muse Wonder | $4/M input, $0.20/M cached input, $20/M output tokens | 3,000 RPM; 4M TPM |
| Muse Image | $0.01/returned generated image | 150 RPM |
| Voice Transcribe | $0.18/audio hour, whole-second metering | 256 concurrent streams; 16,000 streams/hour |
| SAM 3.1 | $2.50/1,000 images; $0.20/1,000 video frames | 3,000 RPM |

Limits are shared per team across keys; separate keys do not create additional capacity. Record usage units and the active price-version identifier; treat cost estimates as estimates until reconciled to billing. Vouch's initial plan prices and gross-margin numbers from the DOCX remain hypotheses. They exclude unmeasured real retries, transport, storage, messaging, taxes, and provider alternatives.

Vouch decision: one team-aware limiter plus tenant budgets; reserve a conservative estimated maximum before paid work, meter actual results, and release unused reservation. Use deadlines and bounded retry policies, honoring provider retry metadata. Never blindly retry every `400`, inaccessible model, invalid input or safety block. Failed/ambiguous generation requests need reconciliation rather than assumed idempotency; provider billing/idempotency guarantees are still unverified.

### Retention contract

Responses defaults to `store: true`. Vouch's proposal is explicit `store: false` on supported single-shot paths, no unnecessary server-managed history, and no raw model payloads in application logs. This controls response state, not all provider operational/security retention. [Responses API](https://dev.meta.ai/docs/protocols/responses)

Files API supports 1 GiB uploads versus 50 MB inline and 100 GiB team storage. Uploaded files do not expire by default. An explicit `expires_after` can use `anchor: created_at` and 3,600–2,592,000 seconds. Proposed Vouch uploads request at most 24 hours and explicit deletion when no longer needed; verify the returned expiry and remote deletion. Maintain a cleanup ledger for every remote file ID, including failed jobs and provider errors. Deleting local storage alone is incomplete. [File handling](https://dev.meta.ai/docs/file-handling)

ZDR requires separate Meta enablement for an eligible organization and may vary by model. It excludes stored file uploads, server-managed state, background requests, web search, and Contributor mode; legal/abuse exceptions still apply. An upload-once video workflow therefore cannot be called ZDR. If a pilot requires ZDR, use only a separately verified compatible input path and organization key, or disable that workflow. [Meta ZDR policy](https://dev.meta.ai/help/policies-and-privacy/zero-data-retention)

The API Terms distinguish retained content for service/security/legal purposes from training use. Do not promise that every Meta-held copy disappears after Vouch's application TTL or API deletion. Confirm the applicable contract and disclose this distinction before handling real customer photos. [API Terms, retention and Standard Services](https://dev.meta.ai/legal/terms-of-service)

## 6. Model keys do not connect business channels

| Integration | Independent setup/access requirement | Initial documentation/mock fallback |
| --- | --- | --- |
| Meta Model API | Team key, models, region eligibility, credits/billing and privacy terms | Deterministic synthetic provider fixtures. |
| WhatsApp | Separate business/app configuration, sender/phone resources, access token, webhook verification and applicable messaging approvals/policy | First-party web Try conversation and signed webhook fixtures. Not a claim of a live WhatsApp integration. |
| Instagram | Separate professional-account connection, app configuration, access scopes/review and messaging permissions | Authorized uploads/manual creator records; no implied broad social graph access. |
| Shopify | Store installation/authorization, scoped Admin access, webhook configuration | Synthetic catalog and order events, explicitly labeled. |
| YouTube | Google project/API credentials, enabled service and account quota; OAuth for authorized operations | Consented creator uploads plus metadata fixtures. |

Shopify's current docs specify scoped access tokens; public GraphQL Admin apps must support expiring offline credentials and token refresh/rotation. Use a tested app-type-specific authorization flow, not the DOCX's generic “connect” endpoint as an auth specification. [Shopify access tokens](https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens)

YouTube's current overview describes separate default daily search/upload allocations and quota for other endpoints. The DOCX's older “100 units per search” assumption must not be embedded as a constant; use the project's effective console quota and current method documentation. A metadata API response does not grant permission to download or process someone else's video. [YouTube API overview](https://developers.google.com/youtube/data/getting-started)

WhatsApp and Instagram primary docs returned HTTP 429 during this review. Their exact test-recipient limits, pricing, conversation/private-reply windows, bot restrictions, fields/scopes and review requirements remain unverified. Record these as channel enablement gates rather than designing an assumed entitlement. See [reference status](../references.md#access-failures-and-not-yet-verified).

## 7. Provider adapter requirements for the later build

These are Vouch contract decisions, not claims that Meta exposes matching SDK methods. Application services depend on capabilities; adapter implementations own provider payloads.

| Contract | Input responsibilities | Normalized result responsibilities |
| --- | --- | --- |
| `Reasoner` | Task type, tenant/job, source asset refs, prompt/schema versions, rulebook snapshot and output schema | Typed facts or judgments, source evidence references, uncertainty, timing precision, incomplete/refused state. |
| `CampaignDossier` | User-requested scope, tenant-authorized evidence snapshot, allowed record IDs, cost/deadline cap | Evidence-linked summary, gaps and human recommendations; no business mutations or approval authority. |
| `Transcriber` | Normalized audio/chunks, source time offsets, allowed vocabulary/language hints | Turns in source milliseconds, text, speaker label if available, language if known, missing-span state. |
| `Segmenter` | One concept or supported object prompts, media ref, dimensions/frame-time mapping | Object tracks/masks, analyzed-frame coverage, empty-match state; never legal/identity conclusions. |
| `TryOnProvider` | Permitted region, consented photo ref, product refs, fixed prompt version | Private generated-asset ref, model/provider, safety/fidelity outcome; no size guarantee. |

Every call carries `organization_id`, `job_id`, logical operation ID, deadline, budget reservation, capability, data classification and region policy. Every normalized result includes schema version, provider/model returned, requested model, invocation mode, start/end timestamps, provider request ID when available, usage units, estimated cost and remote artifact cleanup references. Never log credentials, raw selfies, full transcripts, or signed media URLs as metadata.

Keep geography inputs separate: operator/access location, deployment/processing location, end-user location, evidence source/confidence, and policy version. A permitted deployment region cannot overwrite a restricted operator or end user. Enforce the provider-specific policy before media upload or inference, and deny the capability when required eligibility is unknown. IP hints alone cannot guarantee end-user location; add explicit account/user declarations and risk-appropriate enforcement, without promising infallible geographic identification. Do not route around a policy block.

Invocation mode is explicit: `fixture`, `recorded`, or `live`. Recorded artifacts must carry authorization/provenance and must not be presented as a fresh live result. Unavailable capability cannot quietly become fixture success.

Use the canonical application errors: `NOT_CONFIGURED`, `ACCESS_UNVERIFIED`, `ACCESS_DENIED`, `POLICY_RESTRICTED`, `SAFETY_BLOCKED`, `INVALID_INPUT`, `RATE_LIMITED`, `BUDGET_EXCEEDED`, `TIMEOUT`, `PROVIDER_UNAVAILABLE`, `INVALID_PROVIDER_OUTPUT`, `CANCELLED`, `OUTCOME_UNKNOWN`. A geographic restriction is `POLICY_RESTRICTED`, with a structured reason and relevant region details, rather than a separate `REGION_UNAVAILABLE` error. Reserve `TIMEOUT` for a known outcome with no provider side effect; an ambiguous paid operation is `OUTCOME_UNKNOWN`. Retain its budget reservation until reconciliation establishes the outcome, and do not retry it blindly. Distinguish safe retryable transport failures from permanent refusals/validation/policy failures. Error rendering must not leak secrets or other tenants' data. The [canonical provider ports and call envelope](../architecture/api-contracts.md#7-provider-ports-and-call-envelope) govern these names and semantics.

Keep connection status and per-job status separate. Capability states are `not_configured`, `awaiting_access`, `policy_restricted`, `configured_unverified`, `ready`, `degraded`, `disabled`; jobs use the canonical job state machine in the architecture/data contracts. Maintain these states per provider capability so Spark working does not unlock Muse Image or WhatsApp.

Fixture scenarios must include normal results, inconclusive evidence, incomplete analysis, invalid schema, zero SAM matches, uncertain transcript, corrupt media, 429/timeout, budget denial, policy restriction, safety refusal, cancellation, remote cleanup failure and deletion pending. Use generated/licensed fixtures without personal data; no live calls in default tests.

## 8. October 26 activation checklist

The engineer records sanitized evidence, date, operator and pass/fail for each step. No item is currently checked.

- [ ] Obtain the final event rules and confirm existing/pre-event work, permitted providers, regional eligibility, team/credit conditions and submission requirements.
- [ ] Review current geographic policy with the intended operator, deployment and end-user locations. Keep Muse Image blocked where restricted; obtain provider clarification if an exception is claimed.
- [ ] Confirm team/account, actual key purpose, available models, credit balance, billing caps, region eligibility and Standard-mode selection. Store secrets server-side; never paste them into documentation/chat.
- [ ] Pin the tested SDK versions and actual endpoint payloads inside adapters. Record a dated capability matrix.
- [ ] With synthetic inputs, test Spark schema output, refusal/incomplete paths and actual video visual timestamps. Validate output against application invariants.
- [ ] Test the bounded Wonder dossier against an authorized synthetic campaign snapshot; verify every source ID, uncertainty handling, read-only behavior and spend ceiling.
- [ ] Test Voice multipart format, body-size handling, diarization, source chunk offsets and a few authorized English/Hindi/code-switch samples. Do not infer all-language quality from one successful request.
- [ ] Test SAM image and short video, mask decoding, zero matches, streaming terminal events and source frame/time mapping.
- [ ] Test permitted image generation only if region/policy gates pass. Run the eyewear fidelity evaluation; reject identity changes, wrong SKU/color and implausible placement rather than silently delivering them.
- [ ] Verify `store:false` behavior on chosen paths, upload expiry, remote file deletion and cleanup retries. Confirm provider retention disclosure; do not label the workflow ZDR without enablement and compatible feature tests.
- [ ] Measure latency/usage on representative short clips and image requests; reconcile estimated costs to dashboard/billing. Update budgets and queue concurrency from actual account limits.
- [ ] Exercise timeout/429/5xx safely with fixtures; do not deliberately load-test the provider or spend all credits to discover limits.
- [ ] Separately verify WhatsApp, Instagram and Shopify target accounts/tokens, webhook signatures, replay handling and token refresh before each integration is labeled connected.
- [ ] Record `live` versus `fixture` features for the demo. If gates fail, show the Check/approval flow and clearly labeled preview fixtures; do not fabricate a successful call.

## 9. Open gates and next decision

| Gate | Owner | Evidence needed before enablement |
| --- | --- | --- |
| Final hackathon terms and pre-event eligibility | Team lead | Published rules plus organizer clarification where needed. |
| India Muse Image applicability/alternative | Team lead + integration owner | Current provider policy; any written exception; alternative eligibility, region terms and privacy review. |
| Team model access and limits | Integration owner | Actual October 26 smoke-test log and account limits. |
| Photo processing/retention consent | Product + privacy owner | Accurate provider terms/disclosure, deletion behavior and user consent flow. |
| Try-on fidelity/latency | AI owner | Labeled representative evaluation and explicit pass criteria. |
| Voice/Spark evidence quality | AI + compliance owner | Precision/recall/timing measurements and uncertainty routing. |
| Messaging/channel permissions | Integration owner | Current primary docs, app/account entitlements and approved use case. |
| Full unit economics | Product owner | Measured model + messaging + storage + infrastructure cost, retries included. |

Until these gates are resolved, the build target is an extensible Check-first application with capability-specific adapters and honest unavailable/fixture states. The integration boundary allows Try to become live when a permitted provider and measured quality support the intended users.
