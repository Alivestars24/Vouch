# Vouch backend

Runnable fixture-mode FastAPI API and a separate SQL-backed worker for the first Vouch
workflow. Server-only Meta Model API catalog and bounded Spark smoke adapters are implemented;
product Check still remains fixture-only until its durable live-provider contract is complete.

## Local setup

```powershell
cd services/backend
uv sync --dev
uv run vouch-api
```

In another terminal:

```powershell
cd services/backend
uv run vouch-worker
```

The API listens on `http://127.0.0.1:8010`. The worker and API share the absolute default
database path `services/backend/vouch.db`, even when invoked from another working directory.

To run both processes against local Supabase Postgres, first apply root
`npm.cmd run supabase:migrate`, then set this variable in both terminals:

```powershell
$env:VOUCH_DATABASE_URL = 'postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres'
```

The API/worker use the migration-owned private `vouch` schema. These manual commands use fixture
identity/owner persistence only; recommended real local Auth uses root `supabase:provision` and
`dev:authenticated` with separate restricted API/Check/retention credentials. Both modes reject
staging/production. Existing SQLite data is preserved. Source expiry is reconciled by the separate
`uv run vouch-retention` process (included in root development supervisors).

`VOUCH_MEDIA_MODE=fixture` is independent from identity/provider mode. Optional `decoded` uses the
locally built sandbox image, measured provenance and exact container cleanup. See the canonical
[implementation status](../../docs/engineering/implementation-status.md) for actual setup/proof.

Fixture member requests use both `X-Organization-Id` and `X-Fixture-User`. The user header
accepts a seeded UUID or email; roles are loaded from membership rows and cannot be supplied
by the caller. `X-Fixture-Roles` is rejected.

Seed organization: `11111111-1111-4111-8111-111111111111`. Seed users:

- `admin@vouch.test` (`aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1`), workspace admin only
- `marketer@vouch.test` (`aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2`), marketer
- `reviewer@vouch.test` (`aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3`), reviewer
- `viewer@vouch.test` (`aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa4`), viewer

Use the OpenAPI UI at `/docs`, or export the checked-in handoff artifact with:

```powershell
uv run vouch-openapi --output openapi.json
```

Verification:

```powershell
uv run ruff check .
uv run mypy src
uv run pytest
```

## Meta account capability probe

Keep the Model API credential only in the ignored worker environment, never in browser variables,
source, logs or documentation. Add `VOUCH_META_API_KEY` to `services/backend/.env.worker` and keep
`VOUCH_OPERATOR_REGION=IN` (or the truthful operator region). Then run from the repository root:

```powershell
npm.cmd run meta:probe
```

The command calls the documented `GET https://api.meta.ai/v1/models` endpoint with a server-side
Bearer credential and prints only normalized catalog visibility for Spark 1.3, Voice Transcribe,
SAM 3.1, Wonder and Muse Image. Catalog visibility remains `configured_unverified` until a bounded
synthetic inference passes. Muse Image stays `policy_restricted` for an India operator even if the
catalog lists it. The command uploads no media and does not enable the fixture Check worker's live
path.

After the catalog probe succeeds, the explicit Spark smoke command sends exactly one synthetic paid
request. It accepts no customer text or media, sets `store:false`, uses minimal reasoning, strict
structured output and a 128-token combined reasoning/output ceiling. Meta counts private reasoning
against this same limit; 128 is the smallest live-verified budget for this readiness check:

```powershell
npm.cmd run meta:smoke:spark
```

The command validates the returned model, completed state, non-storage flag, JSON payload and usage
at runtime. A timeout after submission is `OUTCOME_UNKNOWN` and is never retried automatically.
This proves only the Spark Responses transport; it does not switch product Check from fixtures.
