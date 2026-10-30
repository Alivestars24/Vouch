# Vouch

Creator campaigns with evidence, human review and measurable outcomes.

## Architecture diagrams

These Draw.io SVGs contain editable diagram data. Open an image in Draw.io to inspect or edit it.

![Vouch system architecture](docs/diagrams/02-system-architecture.drawio.svg)

| Product and architecture | Workflows and operations |
| --- | --- |
| [Product loop](docs/diagrams/01-product-loop.drawio.svg) | [Authentication and onboarding](docs/diagrams/04-auth-onboarding.drawio.svg) |
| [System architecture](docs/diagrams/02-system-architecture.drawio.svg) | [Creator revision](docs/diagrams/05-creator-revision.drawio.svg) |
| [Trust boundaries](docs/diagrams/03-trust-boundaries.drawio.svg) | [Check pipeline](docs/diagrams/06-check-pipeline.drawio.svg) |
| [Data model](docs/diagrams/08-data-model.drawio.svg) | [Approval binding](docs/diagrams/07-approval-binding.drawio.svg) |
| [Model roles](docs/diagrams/09-model-roles.drawio.svg) | [Retention and deletion](docs/diagrams/10-retention-deletion.drawio.svg) |
| [Deployment topology](docs/diagrams/11-deployment-topology.drawio.svg) | [Demo walkthrough](docs/diagrams/12-demo-walkthrough.drawio.svg) |

**Current state: runnable fixture Check workflow on SQLite or local Supabase Postgres.** The
Next.js web, FastAPI API and separate Python worker share one domain implementation. Postgres
persistence, tenant constraints, approval/deletion guards and desktop/mobile browser flows are
verified. Real local Supabase sign-in, private Storage and separate restricted API/worker logins
now run the same workflow. New uploads require a separate versioned processing-notice acknowledgment;
withdrawal uses durable source/derivative cleanup. Model providers remain fixtures. Hosted deployment
remains gated.

The accepted [Vouch Signal design system](design.md) uses a cool-neutral editorial workspace,
Vouch red and evidence blue, self-hosted UI type and an original optional WebGL sign-in sculpture.
[CI configuration](docs/engineering/ci.md) exists for default checks and opt-in local integration;
GitHub execution is not yet verified.

Vouch connects four modules through one campaign: **Find** creators with authorized evidence, **Check** content against versioned rules, **Try** products through eligible AI preview experiences, and **Track** observed campaign outcomes.

The product targets India plus international markets, with every provider capability gated by operator and end-user eligibility. The Meta account catalog and a bounded synthetic Spark request have been verified; campaign Check execution remains fixture-only until the live product path passes its privacy, quality, cost and regional gates.

## Start here

1. [Documentation index and reading routes](docs/README.md).
2. [Product scope and acceptance criteria](docs/product/requirements.md).
3. [Architecture and boundaries](docs/architecture/overview.md).
4. [Meta model readiness and regional constraints](docs/integrations/meta-api-readiness.md).
5. [Implementation roadmap](docs/engineering/roadmap.md).

The documentation separates accepted product contracts, implementation status and verified external references.

## Local setup

Prerequisites: Node.js 24+, uv/Python 3.14, Docker Desktop, and PowerShell or another shell.
The verified Node version is 24.18.1; the pinned Supabase SDK no longer supports the old Node 20 baseline.
Docker Desktop 4.96.0 was installed and verified on the current machine.

```powershell
npm.cmd ci
npm.cmd --prefix apps/web ci
uv sync --project services/backend --locked
$env:PATH = 'C:\Program Files\Docker\Docker\resources\bin;' + $env:PATH
npm.cmd run supabase:start
npm.cmd run supabase:provision
npm.cmd run supabase:test
npm.cmd run dev:authenticated
```

Open <http://127.0.0.1:3000>. The API defaults to <http://127.0.0.1:8010>; port 8000 was already
occupied on the verified development machine. Sign in as `marketer@vouch.test` to submit, then
`reviewer@vouch.test` to decide/approve. Read the generated password locally from the ignored
`.local/credentials.json`; do not paste secrets into chat. Stop Supabase with `npm.cmd run supabase:stop`.

Provisioning is additive and local-only; it creates ignored separate server env files and public
web configuration. It does not push to the linked hosted project. `npm.cmd run dev` retains explicit
fixture identity with SQLite by default (or loopback Postgres via `VOUCH_DATABASE_URL`). Neither
runtime mode starts with `VOUCH_ENVIRONMENT=production` or `staging`. A separate restricted retention
process now handles anchored expiry and durable Storage/container cleanup. Bounded real-media
decoding is available separately; hosted launch operations remain gates. See the
[media setup and actual verification](docs/engineering/implementation-status.md).

Run local verification with:

```powershell
npm.cmd run check
npm.cmd --prefix apps/web exec -- playwright install chromium
npm.cmd run test:e2e
npm.cmd run test:authenticated
npm.cmd run test:e2e:authenticated
```

See [implementation status](docs/engineering/implementation-status.md) for the exact commands/results,
execution modes, limitations and next step.

When API routes/schemas change, run `npm.cmd run openapi` to regenerate the FastAPI OpenAPI schema and
TypeScript wire artifacts together. `check` rejects stale contracts before testing/building.
Hosted project `neoapucrxhtwlaqzyikn` has verified CLI access, an application schema, private media
Storage and restricted service roles. Hosted development uses ignored environment files and never
pushes fixture users or passwords. Follow the
[environment handoff](docs/engineering/supabase-environments.md) before switching targets.

## Before live integration

Confirm the current official event rules and complete the activation gates in the roadmap before
replacing the verified fixture flow with live adapters.
[Organizer page](https://cerebralvalley.ai/e/meta-ai-developer-hackathon)

**Muse Image is currently restricted for access from India and for integrated products serving end users in India.** This affects Try, even with credentials or overseas hosting. Other capabilities have independent access and policy gates. [Meta policy](https://dev.meta.ai/legal/geographic-use-policy)

Do not interpret fixture tests, prices, latency targets, draft rules or the presence of provider ports
as live product-model coverage. A bounded paid synthetic Spark probe does not establish campaign
media quality or production readiness.
