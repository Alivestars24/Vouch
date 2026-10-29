# Implementation status

Status date: 2026-10-29. This page is the factual handoff for the current build. Architecture
intent lives in the canonical documents; this page records what exists and what was actually run.

## What works

| Capability | State | Execution mode |
| --- | --- | --- |
| Workspace and roles | Real local Supabase password sessions, unique subject mapping, current memberships and server-resolved roles; fixture identity remains separate | Supabase Auth or explicit local fixture mode |
| Campaign setup | Product, authorized creator and rule-pack selection; organization ownership checked | Fixture, local API/UI |
| Authorized upload | Five-minute capability plus bearer scope; 5,000,000-byte cap, MIME/signature validation, rights attestation and separate versioned notice acknowledgment; identical upload retry reconciles bytes | Private Supabase Storage in authenticated mode; database bytes in fixture mode |
| Processing authorization | Immutable purpose/version/hash/member receipt per new asset; legacy read-only cutover, receipt-bound manifests and irreversible withdrawal through deletion | Draft local notice only; not third-party consent or live Meta permission |
| Media validation | Explicit fixture or real bounded Docker decode/transient normalization, measured timeline/provenance and cancellation-aware container cleanup | Local decoded mode; providers remain fixtures |
| Check | Durable accepted operation, separate worker, lease/fence, idempotency, budget hold, per-stage model-call envelopes and typed fixture provider output | Fixture only; call rows are real provenance, not evidence of live provider execution |
| Evidence and findings | Timestamped transcript/visual evidence, missing intervals, rule/version validation, complete/partial assessment | Fixture only |
| Failure behavior | Retry-once success, permanent provider outage with three-attempt dead letter, invalid provider output and budget release; unknown paid outcomes are terminal, not retried, and retain their budget hold | Fixture failure contracts verified locally |
| Human workflow | Reviewer decisions, draft revision note, request changes/reject/approve/revoke, immutable reupload and version comparison | Fixture, local API/UI |
| Approval integrity | Completed coverage, resolved findings, current revision and exact manifest binding; changed decisions invalidate prior approval; current approvals have a permission-checked Markdown report with hashes, provenance, evidence and limitations | Tested on SQLite and Postgres; report route focused-tested on SQLite |
| Deletion | Fences jobs, erases source/text, invalidates approvals, serializes concurrent attachment and guest Storage writes, confirms exact-key Storage absence, retains partial retryable receipts | Local database/private Storage; Meta creates no fixture artifacts |
| Retention | Anchored expiry, system-attributed erasure, separate restricted process, leased/fenced cleanup, three automatic attempts, manual recovery and reloadable receipt history | Local database/private Storage; no live provider copies |
| Supabase persistence | Same API/worker model in private `vouch` schema; composite tenant keys, RLS, migration/column parity | Local Supabase Postgres, tested |
| Data API ownership | Private runtime rejects browser access; separate API/Check/retention/guest logins, transaction scope, RLS and scrub-only guards | 280 SQL assertions, real restricted-login tests and clean local advisors |
| Creator guest | Member issue/revoke/recover/renew, one-time fragment exchange, scoped cookie session, allowlisted submission view, guest-attributed upload/finalize/receipt, initial/later immutable versions, explicit feedback and exact-source withdrawal; exact-byte replay and Storage/deletion fence; no member impersonation | Fixture service tests plus hosted restricted functions; full OAuth/creator browser journey still needs rehearsal |
| Find | Tenant-curated creator evidence with exact-product/category distinction, source/permission/verification/time provenance, filters, evidence-bound roster mutation and draft-only outreach | Local API/UI; synthetic seed evidence; restricted Postgres evidence link is write-once |
| Try | Eligibility decision route blocks Muse Image before photo collection for the India operator and offers safe Find/Check paths | Local UI/policy gate only; no photo upload, generation or alternate provider |
| Track | Campaign-scoped test click/order/refund ledger, stable external IDs, roster attribution, refund bounds, currency totals, raw events and separate test/live summaries | Hosted Postgres plus local API/UI; test input only, no live commerce connector or revenue claim |
| Meta families | Server-only model-catalog adapter, bounded Spark 1.3 structured-output smoke adapter, and normalized roles for Voice Transcribe, SAM 3.1, Wonder and Image; only product Reasoner/Transcriber/Segmenter fixtures execute | Account catalog and one `store:false` Spark call live-verified on 2026-10-27; Image policy-restricted for India; remaining families and product calls unverified |
| Previous hosted project | User reports deleting the previous project on 2026-10-23; cached link is obsolete | Never reuse it; local Auth/database/Storage are independent |
| Replacement hosted selection | User selected `neoapucrxhtwlaqzyikn`; additive application migrations, private Storage and four restricted runtime logins are provisioned without fixture seeds | Localhost uses the hosted database; public deployment/OAuth onboarding/canary remain gated |
| Signal interface | Cool-neutral editorial workspace with Vouch red/evidence blue, self-hosted UI fonts, responsive campaign workbench, truthful real-data overview and loaded-record search; original CSS hero art and optional WebGL sign-in sculpture | Local UI; fixture labels, deferred modules and existing review/consent gates preserved |
| Continuous verification | SHA-pinned default checks and manual local Supabase/browser job definitions | Configuration locally validated; no remote GitHub run |

The UI labels fixture results and keeps analysis lifecycle, machine assessment and human review
visibly separate. No operation publishes content or claims legal certification.

## Curated Find, India Try gate and guest renewal continuation: 2026-10-28

Find is now a routed member surface backed by tenant-owned `creator_evidence`. It exposes source,
permission, verification, collection method and capture time, and never promotes category relevance
to an exact product match. Admins/marketers add a creator with an explicit compatible evidence ID.
The roster stores that evidence; identical replay is safe, a different evidence link conflicts, and
the restricted database policy permits one attachment to a legacy null row but no rewrite. Outreach
is prepared locally and has no delivery side effect.

The `/try` route is an implemented fail-closed India decision, not a generated preview. It renders
the operator policy block before any file input and does not call Muse Image or another provider.
Guest renewal now preserves the original action vocabulary and maximum consumed source/byte counters
instead of failing after an upload or resetting quota. Feedback publication is completed in the
following continuation; a later guest revision, withdrawal, Track and product live Check remain incomplete.

| Actual command/check | Result |
| --- | --- |
| `uv run --project services/backend --no-sync pytest services/backend/tests/test_find.py services/backend/tests/test_sqlite_upgrade.py -q` | 12 passed; tenant/filter/role/idempotency/product mismatch/evidence persistence and additive SQLite upgrade |
| Focused Find/Try/AppShell Vitest command | 9 passed across four files |
| `VOUCH_TEST_AUTHENTICATED=1 ... -k "real_find_links or guest_renewal"` | 3 passed against restricted local Postgres roles; write-once evidence and renewal quota/capability preservation |
| `npm.cmd run supabase:test` with the documented Docker CLI path | 5 files, 259 assertions passed |
| Focused Ruff, backend mypy, frontend ESLint and TypeScript checks | Passed |
| `python -m vouch_backend.openapi` plus `npm.cmd --prefix apps/web run types:api` | OpenAPI and TypeScript wire artifacts regenerated |

No controllable in-app browser was attached for this continuation, so the new Find/Try visual
surfaces are not claimed as desktop/mobile browser-verified. Local web/API health remain reachable.
The exact-byte guest finalize replay, late-Storage-write/deletion race and explicit feedback
publication are now closed in following continuations. The next creator product step is a later
immutable creator revision and scoped withdrawal; Track's append-only test/live-separated ledger and the
durable live Check attempt envelope remain separate incomplete slices.

## Guest replay and Storage deletion fence: 2026-10-28

A lost finalize response no longer strands a validated creator source. The browser retains the same
intent/version idempotency keys while the form remains mounted; a replayed content PUT against a
validated asset now acknowledges only the exact same byte length and SHA-256. It performs no
Storage write and never regresses the asset from `validated`; changed bytes conflict. Finalize and
version publication then use their existing idempotent paths. This recovery remains bounded by the
original five-minute upload capability and active guest session; a browser refresh/crash still loses
the selected file and in-memory keys.

The Supabase guest content path now keeps the tenant-lineage and exact-source database locks through
the bounded private Storage write. Member deletion therefore waits until the object and source state
commit, then erases and confirms the exact key. If the Storage outcome is ambiguous, the database
transaction rolls back and a same-key retry reconciles identical remote bytes; cleanup can still
discover the durable asset/object key. No schema, OpenAPI, RLS grant or migration changed.

| Actual command/check | Result |
| --- | --- |
| `uv run --project services/backend --no-sync pytest services/backend/tests/test_guest_mutation.py -q` | 4 passed; exact validated-byte replay succeeds and changed-byte replay conflicts |
| `VOUCH_TEST_AUTHENTICATED=1 ... -k "real_guest_initial_draft or real_guest_storage_write"` | 2 passed against the restricted guest database role and real local private Storage; deletion blocked at the deterministic pre-write gate, then completed with the object absent |
| Focused backend mypy for `guest_service.py` | Passed |

The deterministic race test first failed because deletion completed while the Storage upload was
paused, proving the old commit boundary. It passed after moving the commit behind the bounded write.
At that checkpoint feedback publication was still open; it is completed in the later continuation
below. Later revision, guest withdrawal and refresh/crash resumability remain open.

## Meta catalog adapter continuation: 2026-10-27

The first provider activation slice is implemented as a server-only, read-only capability probe
plus an explicit synthetic Spark inference smoke.
`VOUCH_META_API_KEY` is secret-valued and excluded from object representations; the client uses the
fixed Meta API origin, disables redirects and environment proxies, bounds the response body, validates
the model-list shape at runtime and maps HTTP/transport failures to safe canonical errors without
reading provider error bodies. The smoke request accepts no caller input, disables storage, uses
minimal reasoning and a strict one-field JSON schema under a 128-token output ceiling. Meta counts
private reasoning and visible JSON against the same budget; live samples proved the prior 64-token
ceiling could end before the JSON was emitted. POST timeouts
become non-retryable `OUTCOME_UNKNOWN`. Missing provider usage remains unknown rather than becoming
zero. The normalized result distinguishes catalog visibility from
verified inference. One acknowledged paid synthetic Spark inference has passed; neither adapter
uploads media, mutates Vouch records or enables a live Check.

| Actual command/check | Result |
| --- | --- |
| `services/backend/.venv/Scripts/python.exe -m pytest services/backend/tests/test_meta_api.py -q` | 36 passed; catalog and Spark request shape, strict/store-off bounds, documented output/optional-usage forms, missing/unknown models, policy restriction, safe HTTP/timeout/outcome semantics, invalid output, format-resilient key validation and secret-redacted representations |
| Focused Ruff check for Meta adapter/config/tests | Passed |
| Focused mypy check for Meta adapter/probe/config | Passed |
| `services/backend/.venv/Scripts/python.exe -m vouch_backend.meta_probe` without a configured key | Failed closed with sanitized `NOT_CONFIGURED`; no network call |
| Spark smoke without acknowledgement, then acknowledged without a configured key | Failed closed with sanitized `CONFIRMATION_REQUIRED`, then `NOT_CONFIGURED`; no network call |
| `npm.cmd run meta:probe` with ignored worker credential | Live account catalog verified Spark 1.3, Voice Transcribe, SAM 3.1, Wonder and Muse Image visibility; Muse Image remained policy-restricted for India |
| `npm.cmd run meta:smoke:spark` with explicit paid-call acknowledgement | Passed with exact model, strict `{status: ok}`, `store:false`, provider request ID and 102 total tokens (26 input, 76 output, 61 reasoning) |

The ignored `services/backend/.env.worker` now holds the operator-provided credential; its presence
was checked without printing or copying the value. The next provider gates are synthetic media
tests for the remaining eligible families plus durable attempt, usage, budget and cleanup records
before any product Check stage becomes live. Catalog/transport success alone does not make Check live.

Hosted target, exact connection checks and migration safety gates are in
[Supabase environments](supabase-environments.md). Prior hosted connection checks are historical;
the user has deleted that project. Current web/API Supabase URLs were checked and remain loopback.

## Setup and run

PowerShell uses `npm.cmd` because the current machine blocks unsigned `npm.ps1`. A newly opened
terminal should inherit Docker's PATH; in the current session the explicit PATH line was required.
Use Node.js 24+ (verified 24.18.1) and Python 3.14/uv. The Supabase SDK requires Node 22 or newer;
the project adopts the actually verified Node 24 baseline instead of retaining Node 20 guidance.

### Authenticated local workflow (recommended)

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

Open `http://127.0.0.1:3000`. Use `marketer@vouch.test` to submit and
`reviewer@vouch.test` to decide/approve. The generated password is in
`.local/credentials.json`; read it locally, never paste it into chat or commit it. Bootstrap creates
six synthetic Auth accounts and separate `vouch_local_api`, `vouch_local_worker`,
`vouch_local_retention` and `vouch_local_guest` logins. Re-running
it preserves generated secrets, unrelated environment settings and existing workflow data.

Generated ignored files: `.local/credentials.json`, `services/backend/.env.api`, `.env.worker`,
`.env.retention`, `.env.guest`, and `apps/web/.env.local`. Only public URL/key configuration reaches the browser.
The cleanup key stays in API/retention env files; the Check worker has no cleanup key. Local owner access
is reserved for provisioning/migrations. Bootstrap refuses non-loopback/unexpected ports/projects.

The authenticated dev supervisor runs web `127.0.0.1:3000`, API `127.0.0.1:8010`, the separate
fixture-provider worker and retention process. HTTP listeners are loopback-only. Browser suites
start/stop their own supervisor; stop any active development server first. Tests intentionally refuse
to reuse a server that could be running the wrong mode. When run in a terminal, stop with Ctrl+C.

### Preserved fixture-only mode

`npm.cmd run dev` explicitly sets both API and web to fixture identity, even after authenticated
provisioning. This is intentionally not a bearer-auth fallback.

```powershell
npm.cmd ci
npm.cmd --prefix apps/web ci
uv sync --project services/backend --locked
$env:PATH = 'C:\Program Files\Docker\Docker\resources\bin;' + $env:PATH
npm.cmd run supabase:start
npm.cmd run supabase:migrate
npm.cmd run supabase:test
$env:VOUCH_DATABASE_URL = 'postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres'
npm.cmd run dev
```

Local addresses:

- Web: `http://127.0.0.1:3000`
- FastAPI: `http://127.0.0.1:8010`
- OpenAPI UI: `http://127.0.0.1:8010/docs`
- Supabase API: `http://127.0.0.1:54321`
- Supabase Studio: `http://127.0.0.1:54323`

The URL shown is the local Supabase development default. The private `vouch` schema is migration
owned; fixture startup seeds synthetic data once, authenticated startup does not seed. Omitting
`VOUCH_DATABASE_URL` in fixture mode uses the preserved `services/backend/vouch.db`. Only this
fixture path uses local owner persistence. Both modes still refuse staging/production; fixture
Postgres URLs must be loopback and cannot target the linked hosted project.

For an existing local stack use `supabase:migrate`, which applies pending additive migrations.
`supabase:reset` destroys local database data and should be used only for an intentional fresh start.

## Current verification: 2026-10-22

Authenticated-foundation continuation (latest code):

| Command/check | Actual result |
| --- | --- |
| `npm.cmd run supabase:provision` | Passed; repeat provision preserves credentials and writes only ignored local configuration |
| `uv run --project services/backend pytest services/backend/tests -o addopts='' -q` | SQLite: 55 passed, 5 opt-in/Postgres skips |
| Same command with local `VOUCH_TEST_POSTGRES_URL` | PostgreSQL: 57 passed, 3 real-Auth opt-in skips; includes expiry and late-attachment/deletion barrier regressions |
| `npm.cmd run test:authenticated` | 3 passed using real local password Auth, caller-token Storage, restricted logins, finding decision/approval/revision/deletion, pool scope, current revocation and sign-out denial |
| `npm.cmd run supabase:test` | 113 SQL assertions passed, 3 files |
| Local `supabase db advisors --type all --level warn` command below | No issues found after consolidating redundant source-lock policy |
| `npm.cmd run check` | Passed: Ruff, ESLint, mypy (17 source files), TypeScript, default tests, 12 component tests, production build and generated bearer-aware OpenAPI |
| `npm.cmd run test:e2e:authenticated` | 6 passed: desktop/mobile full authenticated workflow through Storage deletion, revoked-member boundary, sign-in widths 320/768/1024/1440 and keyboard input order |
| `npm.cmd run test:e2e` with loopback Postgres fixture persistence | 2 passed after authenticated changes; fixture identity remains a separate working mode |
| Final authenticated startup | Web HTTP 200; API `/ready` reports ready/reachable; both listeners bound only to 127.0.0.1; provider mode remains fixture |

The Storage timeout/conflicting-byte/unknown-upload retry and partial-deletion retry failures use
deterministic HTTP/in-memory doubles. The real local integration verifies successful upload/read/
delete and anonymous/cross-tenant denial, not a deliberately broken running Storage service.
Browser tests capture page errors and assert none; authenticated tracing is disabled. Rendered
320px sign-in and mobile approved-version screenshots were inspected. This is not a full assistive
technology/accessibility audit. One existing Starlette/httpx deprecation warning remains; browser
runner output also includes the tool's `NO_COLOR`/`FORCE_COLOR` warning.

The lineage review found and fixed an attachment/deletion race. Reviewer/viewer source locks are
separate from edit permissions; attempted pointer changes/deletion are denied by SQL tests.
During local migration development an initially empty revision-policy file was picked up by a
concurrent bootstrap; the canonical policy was executed once locally and verified afterward.
No history repair/reset was used. A fresh destructive reset/restore drill was not performed.
Canonical-document links and the archived DOCX hash pass. A generated frontend bundle scan found
none of the API cleanup key, runtime DB passwords or generated synthetic login password. Web
`npm.cmd --prefix apps/web audit --omit=dev` reports zero production vulnerabilities.

Reproduce the latest proof (PowerShell):

```powershell
npm.cmd run check
$env:VOUCH_TEST_POSTGRES_URL = 'postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres'
uv run --project services/backend pytest services/backend/tests -o addopts='' -q
Remove-Item Env:VOUCH_TEST_POSTGRES_URL
npm.cmd run test:authenticated
npm.cmd run supabase:test
npm.cmd run test:e2e:authenticated
```

Earlier fixture-persistence proof on the same date is retained below as history; its smaller test
counts and auth limitations do not override the continuation above.

| Command/check | Actual result |
| --- | --- |
| `uv run --project services/backend pytest services/backend/tests -o addopts='' -q` | SQLite: 15 passed, 1 Postgres-only skip |
| Same command with `VOUCH_TEST_POSTGRES_URL` set to the local development URL above | PostgreSQL: 16 passed; includes concurrent worker claims, concurrent budget cap and migration column parity |
| `npm.cmd run check` | Passed: Ruff, ESLint, mypy (15 source files), TypeScript, SQLite tests, 2 component tests, production build and regenerated OpenAPI |
| `npx.cmd supabase migration up --local` | Applied private runtime schema and Data API hardening migrations; no reset |
| `npx.cmd supabase test db --local` | 42 assertions passed across public policy and private runtime isolation tests |
| `npx.cmd supabase db advisors --local --type all --level warn --fail-on none --output-format json` | No issues found in the local database |
| `npm.cmd run test:e2e` with `VOUCH_DATABASE_URL` set to local Postgres | 2 passed: desktop Chromium and mobile Chromium; campaign/upload/partial/denied approval/revision/complete Check/approval/comparison |
| Browser binaries | Playwright Chromium installed locally; tests make no paid calls |
| Local Markdown file links | All resolved after documentation reconciliation |
| Archived source integrity | DOCX SHA-256 matches original recorded value `53D49B4D2692A7AE73AE41D83733CAE949AF39DEDBBA308288239A44B82B4C2D` |

Historical hosted setup checks on this date (project deleted by the user on 2026-10-23): CLI browser login and
`npx.cmd supabase link --project-ref iuxnwiobswrdzimzrunp --agent no` succeeded. Account project
listing reported `Vouch`, `ACTIVE_HEALTHY`, `ap-northeast-1`. An Auth settings GET using the
publishable key returned HTTP 200. Two `supabase db query --linked --project-ref ...` metadata-only
SELECTs found no application base tables in `public`/`vouch`, runtime schema or migration history.
The Supabase connector was not authenticated; CLI authorization succeeded independently. After
linking, `supabase:reset` and `supabase:test` were made explicitly local. Re-running
`npm.cmd run supabase:test` passed all 42 local SQL assertions. Package JSON/scope validation,
changed-document relative links and the archived DOCX hash also passed. No reset or new application
test/build/browser run was performed for this connection/script-scope/documentation change.

The Postgres tests use random local-only `vouch_test_<uuid>` schemas and remove only those exact test
schemas afterward. The existing `vouch` data is not reset. The browser tests create synthetic
campaigns in the runtime schema and automatically start/stop API, worker and web processes.

Reproduce browser verification:

```powershell
npm.cmd --prefix apps/web exec -- playwright install chromium
$env:VOUCH_DATABASE_URL = 'postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres'
npm.cmd run test:e2e
```

## Earlier verification: 2026-10-21

| Command/check | Result on 2026-10-21 |
| --- | --- |
| `docker version --format '{{.Server.Version}}'` | Docker engine 29.9.1 responded |
| `docker run --rm hello-world` | Passed |
| `npx.cmd supabase --version` | 2.121.0 |
| `npx.cmd supabase db reset` | Migration and synthetic seed applied |
| `npx.cmd supabase test db` | 1 file, 7 pgTAP assertions, PASS |
| `uv run --project services/backend pytest -q` | 4 passed; one Starlette TestClient deprecation warning |
| `uv run --project services/backend ruff check services/backend/src services/backend/tests` | Passed |
| `uv run --project services/backend mypy services/backend/src` | Passed, 14 source files |
| `npm.cmd --prefix apps/web run lint` | Passed |
| `npm.cmd --prefix apps/web run typecheck` | Passed |
| `npm.cmd --prefix apps/web run test` | 2 files, 2 tests passed |
| `npm.cmd run setup` | Passed; root/web lockfiles installed and backend lock checked (with documented dev-only npm warnings) |
| `npm.cmd run check` | Passed after final browser fixes: Ruff, ESLint, mypy, TypeScript, 4 backend tests, 2 frontend tests, production build and OpenAPI generation |
| `npm.cmd --prefix apps/web run build` | Passed; `/`, `/icon.svg` static and `/campaigns/[campaignId]` dynamic route built |
| `uv run --project services/backend vouch-openapi` | Generated `services/backend/openapi.json` |
| API and worker startup | API listened on 8010; fixture worker started |
| Playwright browser walkthrough | Passed workspace → campaign → upload → partial Check → blocked approval → revision → complete Check → dismissed finding → exact-version approval → comparison |
| Responsive browser inspection | Passed at 390×844; key controls, evidence, approval and history remained usable |
| Final browser console inspection | Zero errors and zero warnings on a clean campaign page load |

The browser walkthrough found and fixed two state bugs: completed jobs now refetch their final Check,
and a new revision no longer auto-selects the previous version's Check. It also fixed aborted identity
requests being displayed as false network errors.

## Retention continuation: 2026-10-22

The accepted [retention contract](../architecture/retention-worker.md) is implemented locally.
Its process is part of both explicit development supervisors. Existing generated credentials are
preserved; provisioning adds `vouch_local_retention` and ignored `.env.retention` without resetting
data. The cleanup key is server-only in API/retention configuration, never in the Check worker.
Source deadlines never extend. Failed receipts stay incomplete and support authorized manual retry.

| Actual command/check | Result |
| --- | --- |
| `npm.cmd run supabase:provision` | Passed; third restricted login/config added locally, existing credentials/data preserved |
| Focused setup/SQLite upgrade proof | 9 passed; preserves receipt rows, unknown columns, indexes/triggers/FKs and rolls back an injected failure |
| Default backend before final crash-case addition | SQLite 66 passed/5 skipped; Postgres 68 passed/3 skipped; opt-in retention tests were added afterward |
| `uv run --project services/backend pytest services/backend/tests/test_retention.py -o addopts='' -q` | 7 passed: expiry, derivative erasure, restart, retry exhaustion, concurrent claims, stale fences and crash on third attempt |
| `npm.cmd run test:authenticated` (both integration files) | 6 passed with real local Auth/private Storage and restricted API/Check/retention logins |
| `npm.cmd run check` | Passed: lint/types, default tests, 20 frontend tests, production build and regenerated OpenAPI |
| `npm.cmd run supabase:test` | 174 SQL assertions passed; system-role denials and retry-budget/lease guards included |
| Local database advisors after isolated test schemas finished | No issues found |
| Postgres fixture `npm.cmd run test:e2e` | 2 passed, desktop/mobile |
| `npm.cmd run test:e2e:authenticated` | 6 passed; confirmed Storage deletion receipt recovered after reload |

Three additive migrations preserve applied history. Initial verification caught JSON record
equality in triggers; an additive `to_jsonb` repair and further claim-budget guard were applied and
tested. No hosted migration, reset or paid model call occurred. Completed erasure covers declared
active application copies, not backups or unverified provider retention. Work on bounded media
decoding follows this receipt; proof above does not claim the later decoder is verified.

## Media continuation: 2026-10-23

The [media contract](../architecture/media-validation.md) was written before implementation. It is
now implemented with an explicit fixture/decoded setting independent from provider mode. Decoded
mode accepts only the documented 5 MB/30-second/1080p-equivalent/60 fps envelope and supported
zero-origin, constant-frame-rate timing. It rejects unsupported inputs rather than inventing
alignment. Normalized bytes exist only in bounded container tmpfs; measured metadata/hash remain.

The sandbox image uses a digest-pinned official Python base and pinned Debian FFmpeg package.
Runtime resolves the local image to its immutable image ID, refuses remote Docker endpoints and
never implicitly pulls an image. It runs non-root, network-none, read-only, capability-dropped,
resource-limited and without persistent container logs. This is local-development containment,
not a production-isolation certification.

Review found and closed two lifecycle gaps. A prepared empty container is durably source-bound
before bytes enter it; deletion can remove it before a late start, and cannot complete until its
absence is confirmed. Receipt JSON cannot authorize deletion of another source's container:
cleanup resolves tombstoned source records and SQL validates the exact asset/run pairs. Container
cleanup failure remains partial/retryable. Source-row locks do not span decoding or finalization
downloads; the existing bounded content PUT still holds its source lock across Storage upload.

Actual proof before the following authorization slice:

- `npm.cmd run media:build` and `npm.cmd run media:fixture` passed; the fixture is an ignored,
  trusted synthetic two-second blue MP4, not personal media.
- `npm.cmd run test:media` passed (27 tests): real MP4/WebM, AAC audio, corrupt/header-only rejection,
  isolated invocation, watchdog/output bounds and real container cancellation before start/with input.
- Finalization's ten initial focused cases passed; later cleanup/target-substitution tests passed.
- `npm.cmd run check` passed lint/types/default tests, 32 frontend tests, build and OpenAPI.
- PostgreSQL full backend: 103 passed, 11 opt-in skips, before the final target-substitution tests.
- Six real Auth/Storage integration tests passed. SQL suite: 198 assertions; advisors clean.
- Browser: fixture/Postgres 2 passed; authenticated fixture-media 6 passed; decoded/authenticated
  2 passed. Desktop/mobile exercised invalid decode recovery, measured two-second metadata, clearly
  synthetic Check evidence and confirmed Storage/container deletion. Page-error arrays were empty.
  Mobile decoded layout and independent provenance labels were visually inspected.

An initial PostgreSQL `DISTINCT` over the new JSON column failed; selecting unique source IDs
instead fixed the shared deletion query and both failing regressions passed. Initial decoder test
doubles also lacked required immutable image provenance and were corrected. No hosted migration,
real Meta call or paid API call occurred. Subsequent consent work has its own accepted contract
and must be verified separately; the receipt above is not evidence for unfinished authorization.

Decoded local setup (keep ordinary default tests in fixture media):

```powershell
$env:PATH = 'C:\Program Files\Docker\Docker\resources\bin;' + $env:PATH
npm.cmd run media:build
npm.cmd run media:fixture
npm.cmd run test:media
npm.cmd run test:e2e:decoded
$env:VOUCH_MEDIA_MODE = 'decoded'
npm.cmd run dev:authenticated
```

Remove `Env:VOUCH_MEDIA_MODE` to return to default fixture media. Browser suites set their media
mode explicitly; real Auth/Storage alone never implies decoded media or live provider evidence.

## Authorization continuation: 2026-10-23

The [authorization contract](../architecture/processing-authorization.md) was written before code.
New upload intents require separate rights and strict affirmative acknowledgment of the exact
current `campaign_check` notice. Its immutable public registry/version/hash is server-owned;
receipts attribute the verified uploader and new manifests bind their provenance. No legacy asset
was backfilled. Historical hashes/approvals stay readable, but fresh processing/sign-off requires a
new acknowledged upload. Revocation/source deletion/expiry fences pending work and late results.

Admin/marketer withdrawal is deliberate and reuses the existing deletion outbox. Revocation and
erasure intent are atomic; retry uses the same receipt and cannot reactivate or extend retention.
System expiry records no invented human actor. Physical Storage/container cleanup may remain
partial/failed, shown in reloadable history. This is a local draft workspace authorization, not
depicted-person consent, legal review or universal privacy-rights fulfillment.

Actual integrated proof before the following type-generation cleanup:

| Command/check | Actual result |
| --- | --- |
| `npm.cmd run check` | Passed Ruff/ESLint, mypy 20 source files, TypeScript, default tests, 41 frontend tests, production build and OpenAPI |
| `uv run --project services/backend pytest services/backend/tests -o addopts='' -q` | SQLite: 121 passed, 14 opt-in/Postgres skips |
| Same command with loopback `VOUCH_TEST_POSTGRES_URL` | PostgreSQL: 123 passed, 12 opt-in skips |
| `npm.cmd run test:authenticated` | 7 passed: real restricted Auth/Storage plus member withdrawal/repeat and system receipt/audit revocation |
| `npm.cmd run test:media` | Passed all 29 cases, including container cleanup failure/authority substitutions and real cancellation; later explicit-count rerun recorded below |
| `npm.cmd run supabase:test` | 232 SQL assertions passed across 4 files, including 34 new notice-receipt policy checks |
| Local `supabase db advisors --local --type all --level warn --fail-on none --output-format json` | No issues found |
| Postgres fixture `npm.cmd run test:e2e` | 2 passed, desktop/mobile, including separate acknowledgment and withdrawal after exact-version approval |
| `npm.cmd run test:e2e:authenticated` | 6 passed, desktop/mobile, including real sign-in, partial evidence, revision, approval, deletion history and revoked membership |
| `npm.cmd run test:e2e:decoded` | 2 passed: corrupt-file recovery, real two-second decode, synthetic Check labels and withdrawal with confirmed cleanup |

Browser page-error arrays were empty; authenticated traces remain disabled. Focused mobile
notice/provenance/withdrawal screenshots were visually inspected. An apparent skip-link overlay
was reproduced as Chromium's beyond-viewport element-capture artifact: normal viewport state kept
the unfocused link offscreen; keyboard focus revealed it correctly. No speculative CSS patch was
made. This is not a complete accessibility audit.

SQLite reload initially dropped receipt timezone information; normalization at the DTO seam fixed
UTC serialization without rewriting stored dates. Restricted retention also verifies the explicit
receipt flush before its revocation audit. Three additive SQL migrations preserve existing data;
no reset, hosted write, real Meta call or paid API call occurred.

## API contract cleanup: 2026-10-23

The accepted ADR-023 generates TypeScript wire types from local OpenAPI using pinned dev-only
`openapi-typescript` 7.13.0. Every outgoing workflow command now satisfies its generated request
schema; notice and receipt GETs have explicit response models. Other dictionary responses remain
generic and retain fail-closed runtime normalization. Generation adds no runtime SDK or production
dependency and does not make arbitrary response JSON trusted.

```powershell
npm.cmd run openapi          # regenerate FastAPI schema and TypeScript together
npm.cmd run contracts:check # compare both artifacts without repairing them
npm.cmd run check            # freshness, lint, types, tests, production build
```

Freshness checks run before the rest of `check`; missing/stale OpenAPI returns a clear nonzero
status without mutating it. Focused backend schema/generation/authorization tests passed 25 cases.
The generated `const:true` and required purpose/version are checked by compile-time tests; invalid
MIME/scenario choices are tested to make no HTTP request. Initial formatting/TypeScript syntax
errors were fixed, then the actual proof below passed:

| Command/check | Actual result |
| --- | --- |
| `npm.cmd run openapi` then `npm.cmd run contracts:check` | Both artifacts generated; non-mutating freshness check passed |
| `npm.cmd run check` | Freshness, Ruff/ESLint, mypy 20 files, TypeScript, default tests, 45 frontend tests in 9 files and production build passed |
| `uv run --project services/backend pytest services/backend/tests -o addopts='' -q` | SQLite: 132 passed, 14 opt-in/Postgres skips |
| Same command with loopback `VOUCH_TEST_POSTGRES_URL` | PostgreSQL: 134 passed, 12 opt-in skips |
| `npm.cmd run test:authenticated -- -o addopts=` | 7 real local restricted Auth/Storage/retention tests passed |
| `npm.cmd run test:media -- -o addopts=` | 29 passed, including real local Docker cancellation |
| `npm.cmd run supabase:test` | 232 assertions passed across 4 files; no hosted target used |
| Postgres fixture `npm.cmd run test:e2e` | 2 passed after type-generation integration |
| `npm.cmd run test:e2e:authenticated` | 6 passed after type-generation integration; page-error arrays empty |
| `npm.cmd run test:e2e:decoded` | 2 passed after type-generation integration; real Auth/Storage/decoding, fixture providers and withdrawal |

The web full dependency audit and `audit --omit=dev` both report zero vulnerabilities on this date.
The prior five-high development-only audit result is historical, not the current result; no forced
breaking downgrade was applied. Original DOCX SHA-256 remains
`53D49B4D2692A7AE73AE41D83733CAE949AF39DEDBBA308288239A44B82B4C2D`.
Final production-bundle scanning found none of five distinct configured private values (local login,
three runtime database passwords and cleanup key). Relative file links in 24 Markdown files resolve.

Final local startup: `VOUCH_MEDIA_MODE=decoded` with `npm.cmd run dev:authenticated`; web HTTP 200,
API readiness reachable, public draft notice readable and anonymous workspace access HTTP 401.
Web/API listeners are loopback-only. The four-process supervisor runs API, Check worker, retention
and web. Providers remain fixture-only; no cloud project is required. Use the setup commands above
after a new terminal/chat rather than assuming the previous development process is still alive.

## Signal interface and verification automation: 2026-10-23

The accepted [design contract](../../design.md) and [tokens](../../tokens.css) replace the
cream/forest/Georgia prototype with a graphite rail, pale workbench, lime controls, bundled
Space Grotesk/IBM Plex typography and coherent original SVG marks. The existing authenticated
workflow, version/role/notice checks and fixture provenance remain intact. Search filters only
loaded campaign records; action counts sum returned actions, and unavailable data is not zero.

Sign-in has an original native WebGL folded ribbon, not a gallery asset, model call or analysis
indicator. It uses one indexed mesh/draw, a 600px backing-dimension cap, DPR cap 1.5, 30fps bound
and finite 3.2-second motion passes. Pointer/keyboard controls, visibility suspension and static
SVG handle reduced motion, unavailable graphics and context loss. Fonts are bundled OFL assets;
there is no font CDN, texture download, 3D runtime dependency or graphics analytics. This is a
functional graphics check, not a physical-device GPU or frame-time benchmark.

The first integrated checks caught an incorrect variable-font import and absent `matchMedia`;
both were corrected. Browser width checks then identified a 320px navigation overflow despite
document clipping. Navigation now reflows into its own full-width phone row; the test checks body
and document widths rather than hiding the defect. Independent review found two more optional
graphics lifecycle bugs: incomplete media-query listener APIs and voluntary context destruction
preventing motion from resuming. Both are fixed and the original findings were re-reviewed closed.

Actual React/Chromium in-memory preference toggling resumed a draw after
no-preference → reduced-motion → no-preference, with zero GL/page errors. Final unmount deleted
all created buffers (4/4), shaders (4/4) and programs (2/2). These local synthetic diagnostics used
no application server, credentials, network or paid APIs. Fourteen focused graphics tests cover
fallback, cleanup, StrictMode, pointer behavior and live preference changes.

New `e2e/design.spec.ts` is part of authenticated browser verification. It checks local fonts,
keyboard focus, 320/375/414/768/1280/1440/1920px layout, 1280×800 sign-in fit, campaign creation,
loaded-record search/no-match recovery, navigation, static/no-WebGL fallback and live motion
preferences. Screenshots and sampled computed contrast checks supplement, not replace, a full
accessibility audit. Authenticated traces remain disabled; no screenshots or secrets are uploaded.

[Continuous verification](ci.md) and `.github/workflows/verify.yml` add locked default checks and
a separate manually opted-in local Supabase integration job. YAML, expected triggers, full action
SHA pins and no-upload guards were locally checked. No GitHub/Linux execution, repository
publication, deployment or hosted write was performed.

ADR-029 accepts the [creator portal implementation contract](../architecture/creator-portal.md).
The grant/exchange/session/submission foundation, true guest media actors, guest-applicable
notice/receipt and explicit feedback publication are now implemented in later continuations.
Revision, withdrawal and their cleanup races remain unimplemented; no UI implies them.

| Command/check | Actual result for this continuation |
| --- | --- |
| `npm.cmd run check` | Contracts current; Ruff/ESLint, mypy (20 files), TypeScript, default backend tests, 62 frontend tests in 12 files and production build passed |
| `npm.cmd run test:e2e:authenticated` | 14 passed across desktop Chromium and Pixel 5 emulation, including the existing review workflow and new design tests |
| Focused Signal screenshot/contrast browser refresh | 2 passed, one per browser project |
| Postgres fixture `npm.cmd run test:e2e` | 2 passed after the redesign |
| `npm.cmd run test:e2e:decoded` | 2 passed after the redesign; real local decode/Auth/Storage, fixture evidence |
| `npm.cmd run build` after browser verification | Production build passed again |
| Web full audit and `audit --omit=dev` | Both zero known vulnerabilities on the check date |
| Final configured-secret production static scan | Five distinct private configured values; zero matches in 27 static files |
| CI YAML and Markdown links | YAML/two-job triggers/full SHA pins passed local validation; relative file links resolved |

The original DOCX hash is unchanged. Sign-in/workspace/campaign screenshots and computed contrast
samples are preserved only in ignored `.local/design-review/2026-10-23-signal/`. Main and delegated
visual inspections covered 375/1440px. Sampled text contrasts are 7.40–17.49:1; a full accessibility,
all-state contrast, multilingual font or physical-device GPU audit was not performed. Existing
Starlette/httpx and NO_COLOR/FORCE_COLOR tool warnings remain; no forced dependency change was made.

Security handoff: an ad-hoc secret-scan URL-parser error inadvertently printed one generated
local API database credential. The diagnostic was replaced with environment parsing and sanitized
failure output; the successful rescan above emitted only counts. No credential was written into
source/docs and no supplied hosted password was used. Local credential rotation remains pending
explicit approval; do not share that diagnostic log. The separately supplied hosted password in
chat should be rotated by the user before hosted activation. These are distinct credentials.

Final local startup, 2026-10-24: `VOUCH_MEDIA_MODE=decoded` with `npm.cmd run dev:authenticated`.
Web, API readiness and the public draft notice returned HTTP 200; anonymous workspace access
returned HTTP 401. Web/API listeners are `127.0.0.1` only. The API, Check worker, retention process
and web supervisor were left running for UI review. This remains local Supabase, not the newly
selected hosted project.

## OAuth, storage allowance and motion completion: 2026-10-24

The accepted [OAuth, storage and motion contract](../architecture/oauth-storage-motion.md) is now
implemented and locally verified without enabling a provider or changing hosted infrastructure.
The sign-in composition keeps Google visible but disabled by default, explains that email/password
remains available and uses the fixed PKCE callback path. Callback failures remain fail-closed and
scrub sensitive URL state. No Google credentials, consent-screen setup, login submission or remote
provider call was used in this continuation.

Workspace storage now reports its allowance, stored originals, active upload reservations and
bytes awaiting confirmed cleanup separately. Reservation admission remains atomic and scoped to
the workspace; pending cleanup does not release capacity. Fixture rendering identifies its local
database provenance. The SQLite path retains the same accounting contract while PostgreSQL is the
required concurrency authority for authenticated operation.

An isolated fixture startup exposed an additive-upgrade defect in the preserved SQLite database:
new tenant-scoped child foreign keys could reference legacy parent tables that predated the unique
`(organization_id, id)` parent key. Startup now creates only missing equivalent unique indexes on
existing metadata tenant tables before adding children, then rechecks after legacy column upgrades.
The upgrade is idempotent. Normal API startup preserved all sampled aggregate row counts and left
`PRAGMA foreign_key_check` clean; no database reset, row deletion or backfill was performed.

The Signal sculpture's bounded pass now commits its local paused guard when the deadline expires.
Observer tests target the sculpture rather than whichever observer was created last, and direct
coverage now exercises the border beam, activity indicator, document visibility, reduced motion
and cleanup. Live Chromium checks confirmed the finite pass pauses, reduced motion switches to a
static canvas-free state with disabled controls, normal motion can resume and pause again, and the
375px sign-in layout has no horizontal overflow. The graphic remains decorative and never presents
itself as analysis progress.

| Command/check | Actual result for this continuation |
| --- | --- |
| `npm.cmd run openapi` and `npm.cmd run contracts:check` | FastAPI OpenAPI and TypeScript wire types regenerated; drift check passed |
| `uv run --project services/backend pytest services/backend/tests/test_storage_quota.py -q` | 10 passed; the loopback-PostgreSQL concurrency case skipped because no local PostgreSQL test URL was available |
| SQLite upgrade regression suite | 4 passed, including the legacy composite-parent-key case and restart idempotency |
| Focused OAuth/storage frontend suite | 5 files, 43 tests passed |
| Focused Signal sculpture/motion suite | 2 files, 13 tests passed |
| Final `npm.cmd run check` | Contracts, Ruff/ESLint, mypy (21 source files), TypeScript, default backend tests, 18 frontend files/110 tests and the production build passed |
| Isolated desktop/mobile browser verification | Workspace storage and public sign-in rendered at 1440px and 375px; disabled Google, bounded/static motion, layout bounds and zero current console errors verified |

That October 24 shell session could not find Docker/Podman on its PATH, so its PostgreSQL and
authenticated-browser reruns were deferred. This historical limitation is superseded by the
successful local PostgreSQL, restricted-login and real creator-browser evidence below. The linked
hosted project was never used as a substitute.

## Creator read-only guest foundation: 2026-10-25 to 2026-10-26

The bounded creator foundation is now real local behavior. Authorized members can issue, revoke,
recover and explicitly renew a 48-hour invitation for one campaign/rostered creator/submission.
Only SHA-256 secret digests are stored. A separate non-BYPASSRLS `vouch_guest` pool atomically
exchanges the fragment secret once for a 30-minute HttpOnly, SameSite=Strict cookie and returns one
allowlisted submission view. Every read rechecks current issuer authority, immutable tenant scope,
revocation, expiry, submission lineage and source availability.

Issuance requires a client-held UUID recovery identifier. Retrying the same scope or renewing by
grant ID creates a new secret/grant and revokes the complete older grant/session family; no
plaintext secret is retained for replay. Two simultaneous authenticated exchanges produce exactly
one success and one uniform safe denial. Client and token throttles stop writing after their fixed
10/5 attempt bounds; only the restricted retention process prunes records older than 24 hours.
Hosted exposure still needs a deployment-specific trusted-proxy/client-address contract.

The isolated `/creator` route never mounts member providers or the workspace shell. It scrubs the
fragment before exchange, resumes an existing cookie session, validates the exact response shape,
and uses no-store/no-referrer/noindex protections. A real local browser exchange/read/reload passed
at desktop and 320px with no horizontal overflow or console errors; the exact synthetic grant and
attempt were removed afterward. No authenticated trace or secret-bearing screenshot was saved.

| Command/check | Actual result |
| --- | --- |
| Four additive creator migrations through `20261025184940_creator_guest_exchange_recovery_hardening.sql` | Applied to the existing local database without reset |
| `npm.cmd run supabase:test` | 5 pgTAP files, 259 assertions, PASS |
| `uv run --project services/backend pytest services/backend/tests/test_guest_portal.py -q` | 10 passed |
| `uv run --project services/backend pytest services/backend/tests/test_sqlite_upgrade.py -q` | 5 passed; additive restart path remains green |
| Persisted fixture `Database.create_all()` plus SQLite integrity query | Additive guest schema applied without reset; both recovery columns are non-null and `foreign_key_check` reports zero violations |
| Targeted Ruff and `mypy services/backend/src` | Passed; 23 typed source files |
| `npm.cmd run test:authenticated -- -o addopts=` | 9 passed, including separate guest login/pool, recovery and simultaneous two-client exchange |
| Focused creator frontend suite plus lint/typecheck/build | 10 tests passed; all three static/build gates passed |
| `npm.cmd run openapi` | FastAPI OpenAPI and TypeScript wire types regenerated for recovery/renewal |
| Final `npm.cmd run check` | Contract freshness, Ruff/ESLint, mypy (23 source files), TypeScript, the complete default backend suite, 21 frontend files/120 tests and the production build passed |

A delegated diagnostic earlier exposed one ignored local guest database credential. The local guest
database password and privacy HMAC key were explicitly rotated; API/worker/retention/member secrets
were preserved and no hosted resource changed. This is separate from the older local API credential
incident recorded above; that older API credential is not claimed rotated.

The latest Google check still does not work end to end: local Supabase Auth reports
`external.google=false`, no runtime `NEXT_PUBLIC_GOOGLE_OAUTH_ENABLED` value is present and the
rendered option remains disabled. The user's Google Cloud-side setup has not yet been connected to
this Supabase runtime, and no Google consent/login success is claimed.

## Editorial Signal refinement: 2026-10-26

ADR-030 is implemented across the existing sign-in, member workspace, campaign workbench and
read-only creator portal. The revised [design contract](../../design.md) and shared
[tokens](../../tokens.css) replace the earlier graphite/lime presentation with cool canvas
`#F5F7FA`, white surfaces, Vouch red `#930500`, evidence blue `#95BBEA`, editorial headings and
self-hosted UI type. Shared navigation, controls, forms, statuses and responsive behavior now use
the same visual language while evidence, authorization, approval, storage and campaign data retain
different task-appropriate treatments.

The workspace overview summarizes only campaigns, next actions and represented markets returned by
the API; loading or failure renders unavailable rather than zero. Its original CSS creator/product
composition is decorative, not a real creator, campaign result or Try output. Find, Try and Track
remain visibly planned/deferred, while Check links into the implemented campaign workflow. The hero
campaign action opens and focuses the existing form. Campaign search still filters only loaded
records. The sign-in form keeps password authentication and the disabled Google explanation; the
creator route remains isolated from member navigation and does not imply guest mutation support.

Routes, API calls, generated contracts, Auth/tenant authority, processing notice, version lineage,
fixture provenance, finding decisions and human approval rules were not replaced. The first fixture
browser rerun caught an ambiguous accessible name shared by the hero action and form submit; the
hero now has the distinct name `Start campaign setup`, and the unchanged workflow rerun passed.
This refinement is local UI work, not a hosted deployment, live-provider integration, product
evaluation or production certification.

| Command/check | Actual result for this continuation |
| --- | --- |
| `npm.cmd run check` | OpenAPI/generated types current; Ruff/ESLint, mypy (23 source files), TypeScript, the complete default backend suite, 21 frontend files/120 tests and the final production build passed |
| Fixture Chromium flow with `VOUCH_API_PORT=8012` and matching public API URL | 1 passed: authorized draft, partial evidence, revision and exact-version approval |
| Authenticated Chromium suite with `VOUCH_API_PORT=8013` and matching public API URL | 7 passed: real local sign-in/private upload/revision/approval, revoked membership, narrow/tablet/desktop sign-in, 320–1920px design bounds, local fonts, sampled contrast, reduced motion and WebGL fallback/live preference changes |
| Manual rendered inspection | Workspace, campaign, creator ended-link state and sign-in inspected at 1440px; workspace/campaign/sign-in inspected at 320px with no document overflow; reduced-motion sign-in remained static and usable; fresh sign-in had no console warning/error |

The alternate API ports avoided an unrelated user process already listening on the repository's
default port 8010. That process was not stopped or modified. Browser servers started for these
checks were stopped by Playwright; the separate manual Vouch API on port 8011 was also stopped.

## Explicit creator feedback publication: 2026-10-28

Admins, marketers and reviewers can now explicitly publish a selected feedback snapshot from an
exact prepared fix draft. Publication requires the current non-superseded submission version, a
completed/partial Check, active processing authorization, a validated live source and a required
actor-scoped idempotency key. Optional timestamp bounds must be paired, ordered and within measured
duration. The creator portal receives only message/range plus immutable version and Check
provenance; earlier-version feedback is labeled historical. This action does not send a message,
publish content or expose raw findings/reviewer rationale.

The additive Postgres migrations create tenant-composite lineage constraints, restricted RLS and
insert guards. Member deletion and the independent retention role can clear only the message and
range after the exact source is deleted/expired; immutable identifiers/provenance remain. SQLite
uses the shared model/service deletion traversal. Generated OpenAPI and TypeScript wire types were
regenerated for the new command and response.

| Command/check | Actual result for this continuation |
| --- | --- |
| Focused creator-feedback backend suite | 3 passed |
| `npm.cmd run supabase:test` | 5 pgTAP files, 280 assertions, PASS |
| `npx.cmd supabase db lint --local --level warning` | No schema errors found |
| Authenticated integration via `uv run --no-sync` | 14 passed, including restricted API/guest roles, private Storage, replay, creator read and deletion scrub |
| Contract freshness, Ruff and backend mypy | OpenAPI/generated TypeScript current; Ruff passed; mypy passed for 26 source files |
| Complete default backend suite | Passed; authenticated/media opt-in cases remained skipped in this default run and the 14 authenticated tests were run separately above |
| Complete frontend suite | ESLint and TypeScript passed; 27 files/154 tests passed |
| `npm.cmd --prefix apps/web run build` | Next.js 16.4.2 production build passed; eight routes generated |
| Local HTTP and clean-browser sign-in inspection | Web `/`, API `/health` and `/ready` returned 200; sign-in rendered without console errors, and Google remained truthfully disabled |

The running local Auth settings endpoint still reports `external.google=false`; the public Google
enable flag and local provider credentials are absent. Google Cloud-side configuration alone has
not completed the Supabase/app connection, so no successful Google login is claimed.

## Hosted runtime bootstrap continuation: 2026-10-28

The user explicitly authorized the linked hosted project and directed the application away from
local Supabase. The reviewed migration chain was dry-run, then applied without seeds or Vault/config
push. Hosted verification found 35 migrations, 34 `vouch` tables, the private `vouch-media` bucket,
zero Auth users and non-login/non-bypass runtime groups.

| Command/check | Actual result |
| --- | --- |
| `supabase db push --linked --project-ref neoapucrxhtwlaqzyikn --include-all --skip-vault --dry-run --yes` | Clean plan: 35 migrations; no seeds/roles |
| Same command without `--dry-run` | All 35 migrations applied |
| `python -m vouch_backend.hosted_setup --project-ref neoapucrxhtwlaqzyikn` | Passed twice; generated ignored configuration and idempotently provisioned four runtime logins |
| Hosted role/membership query | API, worker, guest and retention LOGIN roles each have exactly one intended group; none is superuser/BYPASSRLS |
| Restricted SSL pooler connection probe | API and guest connected as `vouch_runtime_api` and `vouch_runtime_guest` |
| Focused Ruff/mypy for hosted setup/onboarding | Passed |
| Hosted onboarding CLI help/argument contract | Passed; no user was onboarded because `auth.users` is still empty |
| Focused creator-revision backend tests | 4 passed |
| Focused creator portal/form/transport tests | 3 files, 26 tests passed; TypeScript passed |
| Hosted revision migration dry-run/push | Only `20261028113000_guest_revision_publication.sql`; no seeds/roles; applied successfully |
| Hosted security advisor (`error`) | No issues found |
| Hosted localhost restart | Web `/` and API `/ready` returned 200; restricted database reachable |

No browser OAuth flow, hosted Storage object write, paid Meta call, deployment or production canary
was run in this continuation.

## Test-only Track continuation: 2026-10-29

Track is now a routed module backed by an append-only `outcome_events` ledger. Admins and marketers
can record only explicitly labeled test clicks, orders and refunds for creators already on the
campaign roster. Stable external event IDs make identical replay idempotent and conflicting replay
fail closed. Refunds require a matching test order/currency and cannot exceed its recorded value.
The report returns raw events, freshness and per-currency gross/refunded/net values while keeping
test and live summaries structurally separate. Live remains zero/unavailable until an authorized
connector exists; the UI does not call test value revenue or claim causal lift.

| Command/check | Actual result |
| --- | --- |
| Backend Track tests | 2 passed: identical replay, conflict, order/refund bounds, test/live separation and reviewer denial |
| Focused Track Vitest | 2 files, 3 tests passed: transport normalization/request shape and UI test/live boundary |
| Frontend TypeScript | Passed |
| Focused backend Ruff | Passed |
| `npm run contracts:check` | Passed; FastAPI OpenAPI and generated TypeScript are current |
| Hosted Track migration dry-run/push | Only `20261029090000_track_test_outcomes.sql`; no seeds/roles; applied successfully |
| Hosted security advisor (`error`) | No issues found |
| Hosted-backed localhost restart | API `/ready` and web `/track` returned 200 |

This was a focused implementation checkpoint, not a full regression, responsive browser or
production deployment pass. A live webhook/commerce connector, tracked redirects and ambiguous
multi-source attribution remain deferred.

## Creator-scoped withdrawal continuation: 2026-10-29

The creator portal now exposes a deliberate two-step withdrawal only for the exact current source
receipt. Service validation binds the active guest session, assigned submission and invitation
renewal family; guessed or cross-scope receipt IDs cannot become generic source traversal. Source
access is blocked immediately, authorization is revoked with `guest` attribution, retained review
content is scrubbed, work is fenced and the existing deletion receipt carries pending private
Storage cleanup. The guest receives no table grant or direct Storage-delete authority.

| Command/check | Actual result |
| --- | --- |
| Focused guest mutation backend tests | 5 passed, including exact-source withdrawal, idempotency, guest attribution and content scrubbing |
| Focused guest transport/portal/form Vitest | 3 files passed, including receipt-scoped request and explicit confirmation |
| Focused Ruff/mypy and frontend TypeScript | Passed |
| `npm run contracts:check` | Passed after OpenAPI/type regeneration |
| Hosted withdrawal migration dry-run/push | Only `20261029103000_guest_source_withdrawal.sql`; no seeds/roles; applied successfully |
| Hosted database lint and security advisor (`error`) | No issues found |
| Hosted-backed localhost restart | API `/ready` and web `/creator` returned 200 |

The hosted database currently has no onboarded Auth user/campaign fixture, so the restricted
function could not be exercised end-to-end against a real hosted guest cookie without fabricating
production data. Its migration compiled and linted; the full OAuth → invitation → upload → withdraw
browser journey remains a release rehearsal gate.

## Durable Check model-call envelope and release check: 2026-10-29

Each fixture Check stage now writes a tenant-scoped `model_calls` row before invocation and closes
it with its pinned capability/model/prompt/schema/adapter versions, timing, outcome, request-ID and
usage/cost fields. Successful fixture rows are known-zero-cost and explicitly not live-verified.
`OUTCOME_UNKNOWN` is terminal, is not retried, and retains the original budget hold for later
reconciliation. No customer content or paid product call was sent to Meta.

| Verification | Result |
| --- | --- |
| Focused model-call/retry tests | 3 passed: durable stage rows, retry behavior and unknown-outcome hold/no-retry |
| Hosted migration dry-run/push | Only `20261029120000_durable_model_calls.sql`; no seeds/roles; applied successfully |
| Hosted database lint (`error`) | No issues found |
| `npm.cmd run check` | Passed: contracts, Ruff/ESLint, mypy/TypeScript, backend suite, 29 frontend files/159 tests and production build |
| Hosted-backed localhost | API `/ready` and web `/track` returned 200 after restart |
| Google OAuth handoff | Clean browser reached Google Accounts with the hosted Supabase callback and configured Google client; credential entry and exact-subject onboarding remain user-gated |
| Responsive public surfaces | 390x844 mobile, reduced-motion login and expired creator-link state rendered with expected controls; no unexpected application console error |
| Web deployment boundary | Validated opt-in `VOUCH_INTERNAL_API_ORIGIN` same-origin proxy plus global no-sniff/frame/referrer/opener/permissions headers; lint/build passed and localhost returned the headers |

## Campaign readiness brief and current Meta transport check: 2026-10-30

The campaign workspace now derives a no-store, tenant-scoped readiness brief from current uploads,
Checks, evidence coverage, finding decisions, exact-version approvals and pending cleanup. Every
blocker/action links to its source region. The core brief is deterministic and does not depend on
Wonder, mutate review state or claim legal compliance.

The account catalog probe succeeded for Spark 1.3, Voice Transcribe, SAM 3.1 and Wonder. Muse Image
remained policy-restricted for the India operator. One explicitly authorized bounded Spark 1.3
synthetic call succeeded with strict structured output and `store:false`; it used 26 input and 48
output tokens, including 34 reasoning tokens. This verifies current key/transport access only, not
future billing availability or product-video Check quality.

| Verification | Result |
| --- | --- |
| Readiness lifecycle backend test | Passed across empty, unchecked, finding-blocked, approved, revised and revoked states plus cross-tenant denial |
| Readiness frontend test | Passed for cited navigation, refresh and fail-closed load error |
| Focused Ruff, mypy, ESLint and TypeScript | Passed |
| `npm run contracts:check` | Passed after OpenAPI/type regeneration |

## Known limitations and dependencies

- SQLite fixture and local Supabase Auth/Storage both execute the workflow. Hosted schema/runtime
  provisioning is complete; a real OAuth subject plus explicit operator membership, deployment
  configuration and operational ownership remain gated.
- Google OAuth is selected in the hosted web environment and hosted provider state was reported
  enabled. PKCE/callback failure behavior is covered, but no live Google identity flow or resulting
  exact-subject membership has yet been exercised.
- Fixture identity headers are development-only and are not authentication. Configuration rejects
  staging/production startup instead of relying only on documentation.
- Authenticated media bytes use private Storage; fixture bytes remain in the database. Bounded
  local decoding/transient normalization is implemented; malware scan, reusable normalized
  artifacts and production worker isolation/read authority remain unimplemented.
- Retention cleanup runs locally with bounded durable retry and reloadable campaign history.
  Failed/overdue receipts require operator attention; production alerts, purge SLO and backup
  re-delete/restore remain unverified. Backups/provider copies are not claimed purged.
- Expired sources also block attachment, new Checks, review and late worker publication; version
  history suppresses their captions. Two expiry regression cases exercise pre-Check and in-flight
  expiry. The independent retention process now performs physical database/Storage cleanup.
- Fixture media uses a synthetic ten-second timebase. Decoded media uses measured duration and
  validated identity mapping, but all provider observations/findings remain synthetic fixtures.
- Fixture providers do not establish product-call quality, latency, cost or retention. The Meta
  catalog and one bounded synthetic Spark smoke are live-verified; no customer media/product Check
  has been sent to Meta.
- Muse Image is unavailable for the India fixture context. No alternative provider is selected.
- The creator guest credential lifecycle, upload/finalize, initial/later immutable versions,
  explicit feedback and exact-source withdrawal are implemented and verified in focused tests.
  Live Track ingestion, Wonder execution, webhooks/outbox, exports and real delivery remain deferred. Find is curated
  and local; Try is an India policy gate, not a preview implementation.
- Real restricted API/worker/retention/guest credentials, transaction/pool scope and Storage paths
  are locally tested. Signup/account recovery/MFA, reviewed live notices and
  self-service privacy-rights operations remain separate gates. The browser SDK stores its session locally; failed remote
  sign-out closes the view but displays an unconfirmed-revocation warning.
- Current web production-only and full dependency audits both report zero vulnerabilities;
  this is a dated advisory check, not a guarantee against future findings.
- There is no deployment, backup/restore drill, live monitoring, measured SLO or AI evaluation.
- The previous hosted project was deleted by the user; its credentials/link must not be reused.
  Replacement `neoapucrxhtwlaqzyikn` now has 39 migrations, private Storage and four separately
  restricted runtime logins. No fixture seed/Auth user was pushed. Auth mapping remains empty until
  real OAuth plus explicit operator onboarding. Never push the local known-password seed.
- The Git repository is connected to the private `Alivestars24/Vouch` remote. The initial remote
  verification workflow passed; each later change still requires its own run. Public deployment
  remains a separate gated decision.

Hackathon eligibility is tracked separately in [Meta readiness](../integrations/meta-api-readiness.md).
This pre-event work is not claimed as submission-eligible without confirmed rules.

## Exact next implementation step

The November 3 critical path is now:

1. complete one real Google sign-in, explicitly onboard that exact Auth subject, and rehearse the
   authenticated Find → Check/revision/approval → Track journey;
2. add same-origin deployment, trusted-proxy, monitoring, rollback and production canary evidence
   only with explicit deployment authorization.

Find, fixture Check, the India Try gate, creator revision and test-only Track are usable MVP slices.
The product is not yet production-ready: live Check evaluation, real OAuth onboarding proof,
public deployment and operating evidence remain open. Live Track integration is
not on the demo critical path and must not be simulated as revenue.
