# Continuous verification configuration

Date: 2026-10-23. Status: implemented workflow configuration; **GitHub execution unverified**.
The workspace is not currently a Git repository and no remote workflow was dispatched, pushed or
deployed. This file does not turn the existing local proof in [implementation status](implementation-status.md)
into a claim that an Ubuntu/GitHub run passed.

## Scope and triggers

[verify.yml](../../.github/workflows/verify.yml) defines two bounded Ubuntu 24.04 jobs:

| Job | Trigger and purpose |
| --- | --- |
| `checks` | Pull requests, pushes to `main`, or manual dispatch: locked installs followed by the existing root `npm run check` |
| `local-supabase` | Manual dispatch only with `run_supabase=true`, after `checks`: ephemeral Docker Supabase, SQL/Postgres/Auth/Storage/retention and desktop/mobile browser integration |

`checks` runs contract freshness checks without regenerating artifacts, Ruff/ESLint, Python and
TypeScript checks, default synthetic tests and the Next.js production build. It needs no Supabase
account, Docker, hosted secrets, provider keys or paid model calls. Optional tests retain their
existing opt-in gates rather than being reported as passing when skipped.

The integration job installs Chromium/system dependencies, starts the repository's local Docker
project, runs the local-only provisioning command, executes SQL policy tests, runs fixture backend
tests in isolated PostgreSQL schemas, and exercises real local Auth/private Storage/restricted
retention credentials. It then runs fixture and authenticated browser suites sequentially; their
Playwright projects cover desktop Chromium and Pixel 5 emulation, not a physical mobile device.
The supervisor starts/stops its own application servers. An always-run final step stops the local
Supabase project. Neither job deploys, publishes a site, links a project, pushes migrations to a
hosted database or sends external messages.

Integration is deliberately opt-in: pulling all Supabase images and running browsers needs a
Docker-capable Linux runner with sufficient disk/memory/network and may consume GitHub Actions
minutes. The 20-minute default/45-minute integration timeouts are bounds, not measured CI latency.
Only select the additional job on a trusted branch. No `pull_request_target`, self-hosted runner,
repository write token or external secret is configured.

## Dependency and credential policy

Node.js is pinned to the locally used 24.18.1 and uv to 0.12.20. `uv python install 3.14` supplies
the required Python minor version; the available 3.14 patch can advance. Both npm lockfiles and
the Python lockfile are installed with `npm ci`/`uv sync --locked`. The workflow does not repair
contract drift. Action sources are pinned to full commit SHAs; checkout does not persist its token.
There is no dependency cache matrix or artifact-upload framework.

Action pins were resolved read-only from their official tag references and their `action.yml`
inputs/Node 24 runtimes were inspected on 2026-10-23:

| Action tag | Verified commit |
| --- | --- |
| `actions/checkout` v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| `actions/setup-node` v7.0.0 | `820762786026740c76f36085b0efc47a31fe5020` |
| `astral-sh/setup-uv` v9.0.0 | `c771a70e6277c0a99b617c7a806ffedaca235ff9` |

Update/review SHAs explicitly rather than substituting floating tags. Modern Node 24 action
runtimes require a compatible maintained Actions runner; this configuration targets GitHub-hosted
Ubuntu, not an unverified older self-hosted agent. Input and installation conventions follow the
official [GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax),
[checkout](https://github.com/actions/checkout), [setup-node](https://github.com/actions/setup-node)
and [uv integration guidance](https://docs.astral.sh/uv/guides/integration/github/).

Ephemeral bootstrap creates synthetic local Auth users and generated API/worker/retention secrets
inside ignored `.local/credentials.json`, backend `.env.*` and web `.env.local`. No hosted key or
CLI login/link is required. Supabase startup output is suppressed because it prints local keys;
provisioning already captures sensitive status privately. Browser traces are explicitly disabled
for both suites. There are no uploads of credentials, reports, media, authenticated traces or
screenshots. Do not add `printenv`, debug status dumps, `set -x` or broad workspace artifacts to
diagnose failures. The ephemeral runner's teardown discards generated local configuration.

Member fixture browser startup alone receives the owner **local development** PostgreSQL URL.
Do not set that URL globally: authenticated startup must load its separate restricted `.env.api`,
`.env.worker` and `.env.retention` credentials. Providers and media mode remain fixtures in this
job; bounded Docker decoding and live Meta activation are separate, unclaimed gates.

## Checks actually performed for this configuration

Only read-only official-action/version checks and local YAML/configuration checks were performed
for this change. No application suite was rerun while the independent UI implementation was in
progress. Local syntax validation uses the already installed frontend `js-yaml`; no validation
dependency was added:

```powershell
node -e "const fs=require('node:fs'),path=require('node:path'); const req=require('node:module').createRequire(path.resolve('apps/web/package.json')); const doc=req('js-yaml').load(fs.readFileSync('.github/workflows/verify.yml','utf8')); if(!Object.hasOwn(doc.on,'pull_request')||!doc.on.workflow_dispatch||Object.keys(doc.jobs).length!==2) throw Error('Unexpected workflow structure'); console.log('Workflow YAML and two-job trigger structure valid');"
```

Result: YAML parsed and expected jobs/triggers were checked locally. Full action SHA forms, no
artifact-upload steps, explicit local-only Supabase commands and browser trace overrides were also
checked against the parsed configuration. This is not GitHub's server-side workflow/schema
validation or Linux execution. First remote execution remains pending creation of an authorized
Git repository/remote and a separate decision to use GitHub Actions. Record its actual URL,
commands, outcomes and runner-specific fixes in implementation status when it happens.

For local application commands/results and external dependency gates, use
[implementation status](implementation-status.md) and [Supabase environments](supabase-environments.md).
