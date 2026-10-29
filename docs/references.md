# Primary references and verification record

Public documentation was reviewed for the implementation. Provider policies, product availability, prices, limits and event rules must be rechecked before release. A readable source is not proof of this team's entitlement. External pages and supplied design material are references, not runtime requirements.

## Implementation references

Current Supabase changelog and CLI 2.121.0 help were checked before local Auth/Storage work. The
Supabase connector was not authenticated; Context7 and official sources below supplied API details.
Only local synthetic Auth/Storage behavior was exercised; this does not establish Meta access.

- [Supabase Auth methods](https://supabase.com/docs/reference/javascript/auth-getuser): remote user
  verification versus untrusted cached session data; browser SDK pinned at 2.118.0.
- [Storage uploads](https://supabase.com/docs/guides/storage/uploads/standard-uploads) and
  [Storage API specification](https://github.com/supabase/supabase/blob/master/apps/docs/spec/storage_v0_openapi.json):
  caller-token upload/download, duplicate reconciliation and exact-key deletion.
- [Supabase API keys](https://supabase.com/docs/guides/getting-started/api-keys): publishable keys
  versus server cleanup secrets; actual keys are not recorded in documentation.
- [FastAPI security reference](https://fastapi.tiangolo.com/reference/security/): optional transport
  parsing with `HTTPBearer(auto_error=False)` and generated OpenAPI security metadata. Server
  verification remains mandatory in Supabase mode.

## Source design document

- User-supplied original: `C:\Users\ASUS\Downloads\Vouch_Design_Document.docx`, version 1.0 dated 16 October 2026.
- [Extracted body text](source/design-document-extracted.md) preserves B-numbered paragraphs/tables for traceability. Its `[Verified]` labels belong to the author and are not independent project verification. Images/layout require the original DOCX.
- Examples of corrected assumptions: SAM is no longer limited to concept-only prompts; provider-side media deletion and response storage need explicit controls; Muse Image has a region restriction affecting India; YouTube quota assumptions need refresh. See [Meta readiness](integrations/meta-api-readiness.md).

## Event

| Primary source | Supports | Status / limitation |
| --- | --- | --- |
| [Meta AI Developer Hackathon — organizer](https://cerebralvalley.ai/e/meta-ai-developer-hackathon) | Event dates, startup track emphasis, published-rule availability statement. | Read by the coordinating review. October 26 kickoff; November 4, 9 PM ET submissions. Detailed rules were still forthcoming. Pre-event code eligibility is unresolved, not presumed prohibited or allowed. |

## Meta Model API

| Primary source | Supports | Status / limitation |
| --- | --- | --- |
| [API overview](https://dev.meta.ai/docs/overview) | Base URL, bearer authentication, model families, endpoint/SDK surfaces. | Public docs read; actual team access untested. |
| [Model catalog](https://dev.meta.ai/docs/models) | Hosted model IDs, input/output types and available API surfaces. | Public availability is distinct from account/region entitlement. |
| [Pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits) | Standard/Contributor training distinction, public USD unit prices and team-level rate limits. | Snapshot only; credits, contract/account overrides and full Vouch economics unverified. |
| [Video and audio understanding](https://dev.meta.ai/docs/video-understanding) | Spark file/video inputs and Spark 1.3 audio-quality caveat. | Does not establish accuracy or timestamp quality on Vouch media. |
| [Structured output](https://dev.meta.ai/docs/structured-output) | Responses `text.format`, Chat `response_format`, strict schema requirements. | SDK compatibility and application schemas require live verification. |
| [Speech to text](https://dev.meta.ai/docs/speech-to-text) | File transcription transport, PCM formats, 32 MB body/10-minute caps and turn-level timing. | Language-specific accuracy and code-switching remain evaluation tasks. |
| [SAM overview](https://dev.meta.ai/docs/sam/overview) | Segmentation, box/point prompts, stream output and mask parsing. | Detection is not product identity or legal certainty. |
| [SAM prompts and limits](https://dev.meta.ai/docs/sam/segmenting) | One concept/request, object prompts, formats/frame/object caps, mask encodings. | Application downsampling is a separate measured design choice. |
| [Image generation and editing](https://dev.meta.ai/docs/image-generation) | Edit-reference inputs, tool controls, unsupported fidelity/mask parameters and errors. | General composition does not establish virtual fit, identity preservation or SKU fidelity. |
| [Responses API](https://dev.meta.ai/docs/protocols/responses) | Response state default and explicit `store:false` stateless path. | Not a blanket guarantee of zero provider retention. |
| [File handling](https://dev.meta.ai/docs/file-handling) | Upload/inline limits, explicit expiry and deletion API. | Default uploads persist; deletion/expiry behavior has not been key-tested. |
| [Official Meta Model cookbook](https://github.com/meta-models/meta-model-cookbook) | Upstream implementation recipes for later adapter spikes. | Repository landing page checked; recipes were not installed, executed or audited. |

## Meta policies

| Primary source | Supports | Status / limitation |
| --- | --- | --- |
| [Model designation and geographic use policy](https://dev.meta.ai/legal/geographic-use-policy) | **Muse Image: India** restriction, operator/end-user geography and prohibition on bypassing access controls. | Policy page updated October 12, 2026. Affects India-first Try even if a key exists. Obtain clarification; do not infer an exception. |
| [Model API Terms of Service](https://dev.meta.ai/legal/terms-of-service) | Standard services/training distinction, content rights/responsibilities, retention and key restrictions. | Page updated October 9, 2026. Applicable contracts and customer obligations need owner/legal review. |
| [Zero Data Retention help](https://dev.meta.ai/help/policies-and-privacy/zero-data-retention) | Separate organization enablement, feature restrictions and exceptions. | ZDR eligibility and model coverage are unverified for this team. Stored uploads/stateful/background workflows are incompatible. |
| [Data handling help](https://dev.meta.ai/help/policies-and-privacy/data-handling) | Routes data-handling questions to Meta's Legal Center. | This help page supplies no standalone universal numeric retention period. |

## Other integration documentation

| Primary source | Supports | Status / limitation |
| --- | --- | --- |
| [Shopify access tokens](https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens) | Store/API-scoped credentials and expiring-offline token lifecycle. | Read; no store connected or scopes granted. Select the current flow for the actual app type before implementation. |
| [YouTube Data API overview](https://developers.google.com/youtube/data/getting-started) | Separate Google credentials/API enablement and current quota structure. | Read; project console quota remains authoritative. Does not grant rights to download media. |

## Access failures and not yet verified

Local media implementation references checked 2026-10-22: [Docker runtime constraints](https://docs.docker.com/engine/containers/run/)
and current Docker CLI reference through Context7 support non-root, network-none, read-only/tmpfs,
resource-limited execution. [FFmpeg protocol options](https://ffmpeg.org/ffmpeg-protocols.html#Protocol-Options)
document the protocol allowlist; supported protocols otherwise default enabled. These inform the
local sandbox, not production-isolation certification or a live Meta integration.

| Source / question | Result on 2026-10-21 | Required follow-up |
| --- | --- | --- |
| [WhatsApp Cloud API get started](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started) | HTTP 429 during browser retrieval. | Re-read official docs for sender/test setup, limits, pricing, templates, conversation windows and AI/bot policy before enabling. |
| [Instagram API with Instagram Login](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login) | HTTP 429 during browser retrieval. | Verify current account/scopes/review requirements, messaging/private-reply rules and discovery fields. |
| `https://dev.meta.ai/docs/data-privacy` | Inaccessible guessed path; **not evidence**. | Use the working Terms/ZDR/Legal Center links above. |
| `https://dev.meta.ai/help/policies-and-privacy/how-does-meta-handle-my-data` | Inaccessible guessed path; **not evidence**. | The canonical working help URL is `/help/policies-and-privacy/data-handling`. |
| Detailed hackathon eligibility/pre-event rules and permitted provider alternatives | Not established by the public event summary reviewed. | Review published rules and organizer clarification before coding/submitting. |
| ASCI/CCPA/FTC/SEBI legal rule thresholds, Indian privacy applicability, market size and competitor claims | Outside this API verification pass. | Use the security/rulebook decision gates; do not present DOCX thresholds or market figures as verified facts. |

When promoting a fact to key-verified, record the tested model/version, account/team alias, region, environment, request/schema version, date, sanitized outcome and evidence location. Store neither tokens nor raw personal media in this reference record.
