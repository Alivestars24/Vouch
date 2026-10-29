# Startup strategy and extension priorities

Status: proposed hypotheses, 2026-10-21. No interviews, design partners, paid customers, revenue, conversion lift, market sizing or product metrics have been established by this work.

## 1. Product wedge and value hypothesis

The source has a coherent long-term campaign platform but two different buyers: marketers seeking conversion and reviewers seeking evidence/control. Selling all four modules before finding the strongest pain will make onboarding, evaluation and pricing harder.

Recommended initial wedge: agencies or brand teams that repeatedly review creator drafts. Demonstrate a shorter review/revision cycle with traceable evidence and named human sign-off. This is an operational decision-support product, not compliance certification. Keep product previews as a separately measurable, eligibility-gated value proposition rather than assuming they prove the review business.

The user confirmed startup quality and broad model use. A strong result is a product people repeatedly trust to complete a workflow; five model calls alone do not establish product value.

## 2. Validation work alongside engineering

Suggested first cohort: 5–10 interview participants across small brands, agency operators and reviewers; target 2–3 opt-in design partners before expanding scope. These are proposed research goals, not claimed customers.

Interview around an actual recent campaign: who submits, who reviews, what causes revisions, what evidence is needed, what existing software costs, how long approval takes, and who can authorize a paid pilot. Ask for rights-cleared example failures and existing review criteria, not an unrestricted media dump.

For a supervised pilot, record baseline manual time, Vouch-assisted time, missed issues, false alarms, repeat use, support effort and all processing costs. Do not promise a percentage improvement until measured. Reviewer agreement and downstream errors matter more than an appealing model-generated summary.

A permitted Try pilot measures eligible users entering the flow, completed/acceptable previews, buy clicks and verified orders separately. A preview click-through change is not proven causal sales lift; use an appropriately designed experiment before that claim.

## 3. Prioritize these product improvements

| Priority | Improvement | Why it can create durable value | Evidence before expansion |
| --- | --- | --- | --- |
| P0 | Evidence timeline + revision comparison + approval history | Makes the daily workflow useful and defensible | Faster complete review with low missed-issue rate. |
| P0 | Tenant/role security, deletion and cost controls | Required to trust real media and spend | Actual boundary, cleanup and recovery tests. |
| P1 | Reusable campaign briefs and brand-policy templates | Reduces setup and improves consistent reviewer expectations | Pilot users reuse templates successfully. |
| P1 | Bounded Wonder evidence dossier | Synthesizes a campaign's actual state into human next actions | Validated citations; no unsupported facts; reviewer usefulness. |
| P1 | Creator portal with clear fixes and secure reupload | Removes revision friction without a full creator social network | Fewer clarification messages and faster resubmission. |
| P1 | Verified commerce attribution | Connects observed campaign activity to accountable outcomes | Reconciled orders/refunds and visible attribution coverage. |
| P2 | Licensed discovery and audience fit | Scales sourcing once evidence matters to buyers | Data rights, quotas and measurable match precision. |
| P2 | Region-supported Try across more categories | Adds conversion utility where demand and policy support it | Fidelity, consent, adoption and full unit costs. |

Avoid cross-tenant creator scores, automatic legal decisions, synthetic endorsements, autonomous outbound messages and a broad creator marketplace as early shortcuts. Each adds trust/operations needs beyond the current validated workflow.

## 4. Pricing and economics

The original $79/$299/$699 plan ladder, market sizes and margins remain source hypotheses. Do not publish them as validated pricing or describe unknown cloud/message/model costs as free.

Start pilot pricing discovery from actual value and a transparent allowance: draft volume, reviewer seats, retained media, enabled capabilities and capped overage. Keep feature entitlements separate from consumed units; a failed assessment can still cost the business money, while the customer billing policy must be explicit.

Track per action: normalized media minutes, visual frames/concepts, input/output/cached tokens, generated images and retries, provider fees, channel delivery, storage/egress, worker time and payment/tax/support overhead. Persist known currency and pricing versions; no invented USD/INR conversion.

Budget reservations must include worst-case allowed attempts. Monitor gross margin under full allowance use, burst concurrency and failed jobs, not just the ideal first success. Wonder is on demand with a separate ceiling; don't run it automatically on every small action.

## 5. Differentiation to earn

The strongest potential advantages are a trusted revision/review workflow, relevant reviewed rule packs, authorized evaluation labels, multilingual error analysis and reliable integration into a customer's daily process.

Meta models provide capabilities; they are not an exclusive moat. Use each family where it improves a measured outcome. Keep model alternatives behind tested adapters so platform access/policy changes do not erase the entire product.

Cross-customer learning is not implicit permission to pool videos or creator histories. Aggregate or train only under explicit agreements and privacy controls, and never let tenant retrieval cross boundaries.

Competitor and market claims in the source need a separate current primary-source review before an investor/customer deck. Trademark/domain availability for Vouch also remains unresolved.

## 6. Founder dashboard

Review these weekly during pilots, with definitions and sample counts:

- Activation: first complete review and time to first useful finding.
- Retention: active reviewers/workspaces and repeated campaigns, not one-off demo signups.
- Quality: missed seeded/real issues, disputed findings, reviewer agreement and language/category slices.
- Workflow: submission-to-decision time, revision loops, and creator clarification burden.
- Reliability/privacy: failed stages, backlog age, overdue cleanup, policy blocks and support incidents.
- Economics: settled/unknown costs, spend per successful workflow, support burden and paid willingness.
- Outcomes: verified attributed orders/refunds, unmatched share and eligible Try completion; never assumed lift.

## 7. Decisions to resolve before paid pilots

Choose the first buyer, one measurable outcome and an initial reviewed rule pack. Assign privacy/security and legal review ownership. Agree retention/deletion and provider disclosures, supported markets, support expectations, full-cost budget, pilot pricing and data-use permissions. Validate operational recovery and export needs before promising enterprise capabilities.

The [roadmap](../engineering/roadmap.md) converts these priorities into build gates. The immediate next step is the first complete campaign-to-review slice, with live model activation following eligibility and evaluation.
