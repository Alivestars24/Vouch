# Vouch documentation

Updated: 2026-10-29. A fixture workflow runs on SQLite or Supabase Postgres and is verified
through desktop/mobile browser tests. Real local Supabase Auth/private Storage and restricted
API/worker credentials, anchored retention, optional bounded media decoding and versioned
processing authorization/withdrawal are implemented. Providers remain fixtures and hosted
deployment remains gated. The original source archive is preserved; current proof is recorded in
the implementation ledger, separately from each accepted architecture contract. The 2026-10-26
editorial Signal refinement is implemented across sign-in, workspace, campaign review and the
read-only creator portal; CI configuration exists but has no remote run. Creator access now has a
bounded local invitation/recovery/exchange/session portal plus guest-attributed upload, immutable
processing receipt and initial draft publication. Explicit member-selected feedback publication is
implemented with creator-visible provenance, historical labeling and deletion scrubbing; later
creator revision and exact-source guest withdrawal are implemented. Curated Find, the India
fail-closed Try eligibility route and a test-only Track ledger are implemented. Track keeps test
clicks/orders/refunds separate from an empty live ledger and never labels test value as revenue.
The replacement hosted Supabase target is bootstrapped with restricted runtime roles and the
application migration chain; localhost currently uses that hosted database. Public deployment,
OAuth/onboarding proof and production operations remain gated. See the environment handoff.

## Reading routes

| Need | Canonical document |
| --- | --- |
| What to build, who uses it, what counts as done | [Product requirements](product/requirements.md) |
| Screens, journeys, accessible design and failure states | [Experience design](design/experience.md) |
| Accepted cross-screen visual system, tokens and motion | [Vouch Signal design system](../design.md) |
| System boundaries, model roles and background work | [Architecture](architecture/overview.md) |
| Current accepted auth, database-role and private-media slice | [Authenticated foundation](architecture/authenticated-foundation.md) |
| Google entry, workspace storage allowance and requested motion | [OAuth, storage and motion](architecture/oauth-storage-motion.md) |
| Anchored expiration, system authority and durable cleanup retries | [Retention worker](architecture/retention-worker.md) |
| Decoder bounds, source-time mapping and transient normalization | [Media validation](architecture/media-validation.md) |
| Immutable notice acknowledgment, withdrawal and legacy cutover | [Processing authorization](architecture/processing-authorization.md) |
| Implemented scoped invitations, initial guest upload/draft and explicit feedback; later guest lifecycle | [Creator portal](architecture/creator-portal.md) |
| Entities, lifecycle states and invariants | [Data model](architecture/data-model.md) |
| HTTP operations, payloads and provider interfaces | [API contracts](architecture/api-contracts.md) |
| Why a decision was proposed or accepted | [Decision log](architecture/decisions.md) |
| API access, model eligibility and October 26 activation | [Meta readiness](integrations/meta-api-readiness.md) |
| Privacy, permissions, deletion and abuse prevention | [Privacy and threat model](security/privacy-and-threat-model.md) |
| Evaluation, testing, launch and incident response | [Quality and operations](engineering/quality-and-operations.md) |
| Default checks and opt-in local integration automation; remote run pending | [Continuous verification](engineering/ci.md) |
| Build order and feature gates | [Roadmap](engineering/roadmap.md) |
| What runs, commands/results, limitations and exact next step | [Implementation status](engineering/implementation-status.md) |
| Local versus hosted Supabase, verified link and secret handling | [Supabase environments](engineering/supabase-environments.md) |
| Validation, differentiation, economics and extensions | [Startup strategy](product/startup-strategy.md) |
| Source corrections and unresolved assumptions | [Source review](source/review.md) |
| Dated external facts and access failures | [References](references.md) |
| What was checked in this documentation stage | [Review receipt](engineering/documentation-review.md) |

Read the index plus the documents needed for a task. The [source extraction](source/design-document-extracted.md) is an archive to consult for traceability, not default prompt context. [Original DOCX](source/Vouch_Design_Document.docx) is preserved unchanged, including its two visual figures.

## Status vocabulary

- **User-confirmed:** explicit direction from the conversation.
- **Source-stated:** in the original DOCX; not newly verified.
- **Proposed:** our recommendation for implementation or validation.
- **Publicly documented:** checked against a dated linked primary source; no authenticated behavior established.
- **Implemented:** code or schema exists locally; this does not imply it was exercised.
- **Verified:** the named local command or interaction passed and is recorded in implementation status.
- **Key-verified / measured:** requires reproducible evidence from the actual account/evaluation. Meta catalog access and one bounded Spark structured-output transport call are key-verified; product Check and the other eligible model families are not.

The product contract is split by responsibility: requirements govern intended behavior; data/API documents govern interfaces and invariants; design governs presentation; accepted ADRs explain intentional changes. If two disagree, reconcile them before dependent implementation rather than assuming a silent override.

## Change process

For a material decision, update its ADR status and affected requirements/contracts in the same change. Record the evidence and the date of provider-policy checks. Leave hypotheses labeled until measured. Do not overwrite the source archive when the design evolves.

For each later build slice, reference requirement IDs, relevant ADRs, actual verification and remaining gates. Replace placeholder status with evidence; never turn a target into a claim because a demo looks plausible.

## Open decisions

The event rules and pre-event implementation eligibility, actual account capabilities, deployment region/provider plans, legal review of rulebooks, pilot retention agreement, alternative India Try provider and model quality all remain unresolved. Owners and activation evidence are in [Meta readiness](integrations/meta-api-readiness.md) and [roadmap](engineering/roadmap.md).
