# Kiez-py implementation handoff

Updated: 2026-09-15, Europe/Berlin. Prepared after an interrupted implementation session, by inspecting the workspace and the saved session transcript. No implementation changes or test reruns were made while preparing this handoff.

## Where we stand

The initial Berlin-only clone is implemented: retained Next.js/React UI, a modular Python API, PostgreSQL persistence, and a separate durable AI worker. Final backend and browser suites passed. The prior session was finishing verification and intended to leave the clone running at **http://localhost:3001**. It did not reach its final delivery message.

**Exact interruption point:** `frontend/tests/browser-health.mjs` had just been written and launched. Its result was not collected in the saved transcript. The same final tool call did collect the successful eight-test Playwright result. Check the runtime/hydration script next; do not assume it passed.

The workspace root is **not a Git repository**. There is no commit/diff baseline here; preserve these files. The user requested a handoff and pause because the session was interrupted and their usage allowance was low. The cause of the interruption has not been verified.

## Scope and decisions

- Technical project name: Kiez-py; visible product: Kiez Notes.
- Preserve the original frontend design and interaction flow.
- Four Berlin neighborhoods: Graefekiez, Reuterkiez, Bergmannkiez, Schillerkiez. Hamburg/HafenCity are excluded.
- Reading and text publication work without hosted accounts or AI keys.
- Speech recognition, language detection, translation, speech synthesis, and Chronicle generation have separate provider interfaces.
- Existing Gemini/OpenAI adapters are compatibility implementations. Provider replacement, speed/cost evaluation, Chronicle quality improvements, and official Berlin boundary review are later workstreams.
- PostgreSQL is implemented; PostGIS is deferred.

Read [SPECIFICATION.md](SPECIFICATION.md) for the agreed requirements, [the root README](../README.md) for setup and overview, and [the engine README](../engine/README.md) for operational guarantees and limitations.

## Implemented components

- `frontend/`: retained pages, styles, map, diary, composer, archive, listening and translation controls; Python API proxy and server read client. Draft retention, location checks, cross-Kiez posting, editable voice transcript review, asynchronous job polling/cancellation, and Arabic direction handling.
- `engine/app/api/`: HTTP contracts, validation, feature availability, origin/session checks, rate limits, moderation/admin and cron endpoints, health/readiness and metrics.
- `engine/app/security/`, `neighborhoods/`, `contributions/`, `moderation/`: signed sessions/presence, shared map/location catalog, idempotent publication, Berlin-day latest contribution behavior, retained historical sources, reports/removal and visibility checks.
- `engine/app/ai/`: feature protocols, provider registry/adapters, HTTP transport/error classification, WAV handling, and three-stage Chronicle workflow with source coverage/review gates.
- `engine/app/jobs/` and `chronicles/`: PostgreSQL queue, independent workers, lane concurrency, leases/heartbeats and ownership fencing, bounded retries, task budgets, cancellation, staged audio cleanup, scheduling and guarded publication.
- `engine/migrations/`: `001_initial.py` and `002_provider_metadata.py`.
- `engine/data/` and seed service: four-area catalog, 160 fictional contributions in five languages, 16 editorial Chronicles, stable demo anchor, idempotent startup seeding and explicit demo reset preserving real contributions.
- `scripts/dev.py`, Dockerfiles and `compose.yaml`: local launcher and container setup.

### Last fixes and improvements before interruption

- Added AI request UUID idempotency keys scoped to operation/session. A final backend test caught missing transcription deduplication wiring; this was fixed, then all 53 tests passed.
- Added bounded `/api/featured-chronicles` lookup (at most three public cards in one query), removing per-neighborhood archive requests from the home page.
- Added/fixed provider metadata on editorial fixtures and distinct cron OpenAPI operation IDs.
- Adjusted the Leaflet selected-center effect dependencies.
- Corrected a browser test to expect the existing Kiez missing-page wording. The final eight-scenario run passed.
- Confirmed the original frontend stylesheet was preserved byte-for-byte.

## Confirmed verification from the previous session

Times below are local Berlin time on 2026-09-15. These are recovered results, not newly rerun checks.

| Check | Recorded result |
| --- | --- |
| Backend pytest, including real PostgreSQL integration tests | **53 passed in 2.19s**, collected at 10:44:56; no skips reported |
| Ruff | **All checks passed**, at 10:44:40 |
| Frontend standalone TypeScript check | Exit 0, at 10:39:59 |
| Final frontend production build | Exit 0, collected at 10:44:40; compilation, TypeScript, page generation and traces completed |
| Final Playwright suite | **8 passed in 21.6s**, collected at 10:45:56 |
| Shared-style comparison against original local Kiez | Exit 0, at 10:42:11; shared desktop typography, colors, spacing and borders matched; desktop/mobile screenshots captured |
| Browser runtime/hydration script | Launched at 10:45; completion result **not collected** |

Backend coverage includes sessions/location/boundary versions, concurrent idempotency, moderation and generation races, fixture reset, Berlin midnight/DST, provider error/fallback contracts, WAV output, queue ownership/cancellation/expiry, budget/lane isolation, scheduler stability and stale-worker publication fencing.

The eight browser scenarios cover discovery/archive/keyless AI errors; location-gated publication and idempotency; mobile overflow and keyboard composer; Berlin-only search and location rejection; draft recovery after failed publication; cross-Kiez routing and retained draft; mocked Arabic translation/cancellation; and simulated microphone recording with editable transcript before publication.

Evidence still on disk:

- `engine/.pytest_cache/v/cache/nodeids`: 53 test cases; `lastfailed` is `{}`.
- `frontend/test-results/.last-run.json`: `status: passed`, no failed tests.
- `frontend/test-results/home-desktop.png` and `home-mobile.png`.
- `frontend/.next/BUILD_ID`: production build artifact.
- Visual parity screenshots were generated under `frontend/test-results/parity/`, but are no longer present after the final Playwright run. Recover/regenerate if needed; the successful comparison is recorded in the transcript. This comparison checks shared computed styles, not exhaustive pixel parity for every state.

## Local environment and restart

At handoff inspection, listeners were present on PostgreSQL **127.0.0.1:55432**, API **127.0.0.1:8000**, and frontend **3001**. The previous launcher also reported the worker started. Worker liveness was not independently checked in this handoff; processes may stop when the session closes.

The dedicated local PostgreSQL 17 cluster is in `.data/postgres`. The ignored `engine/.env` already holds local configuration; preserve it and do not copy secrets into documentation. This development cluster uses loopback trust authentication. Docker uses a separate database setup.

If PostgreSQL is stopped, from the workspace root:

```sh
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D "$PWD/.data/postgres" -l "$PWD/.data/postgres.log" -o '-p 55432 -h 127.0.0.1 -k /private/tmp' start
```

If the app is stopped, from the workspace root:

```sh
python3 scripts/dev.py
```

The launcher migrates, seeds idempotently, and starts API, worker and frontend. Avoid starting duplicate processes if the ports are already occupied. Open http://localhost:3001. A location rehearsal for Graefekiez uses latitude **52.4917**, longitude **13.4150**, accuracy **10**.

## Resume checklist

1. Read this file and the root/engine READMEs; inspect the running services before restarting anything.
2. Resolve the uncollected final check, with the app running:

   ```sh
   cd frontend
   node tests/browser-health.mjs
   ```

   This launches local Chrome, checks mobile home/diary/archive and composer dismissal for runtime/hydration errors, and aborts external map tiles. It may require sandbox permission to launch Chrome. Fix an actual failure if found; rerun only the relevant checks.

3. Give the user a concise delivery summary and the local URL after the remaining check. Do not repeat the entire already-passing suite solely because the session restarted.
4. If further acceptance review is requested, compare [SPECIFICATION.md](SPECIFICATION.md) section 11 with the existing tests. Full tablet/reduced-motion/all-state visual acceptance and live multilingual provider quality are not established by the recorded checks.
5. Keep later provider/boundary/PostGIS work separate until the user resumes that scope.

For future changed-code validation: backend commands are `uv run pytest -q` with `TEST_DATABASE_URL` explicitly pointing to a dedicated database whose name ends in `_test`, and `uv run ruff check app tests`, from `engine/`. Frontend commands are `npm run typecheck`, `npm run build`, and `npm run test:e2e`, from `frontend/`. Without `TEST_DATABASE_URL`, integration tests skip; that is not a full run. Browser tests publish test-visitor contributions into the running instance, so use a dedicated instance if real visitor data matters. Avoid resetting current data to tidy up test submissions.

## Remaining limitations / unverified work

- Live AI model access, multilingual quality, latency and cost require a credentialed rehearsal. Fake-provider and mocked browser tests do not establish these.
- Docker/production deployment success is not established by the final local test results; no deployment is claimed.
- Existing boundaries remain illustrative. No PostGIS migration or replacement-provider benchmark has been done.
- Interactive job results expire after 15 minutes; no reusable translation/audio cache yet. Provider billing is not exactly-once; task budgets count tasks rather than monetary cost. Audio backup/WAL retention remains an infrastructure concern.
- No Git commit or publication is claimed.

## Recovery provenance

Previous implementation session transcript (local, may contain sensitive tool output; do not publish):
`/Users/ulrike/.codex/sessions/2026/09/15/rollout-2026-09-15T09-31-59-01a0a3fa-d391-7801-b23b-6f8da78c3dd8.jsonl`.

The final recorded tool result is at 08:45:56 UTC / 10:45:56 Berlin. It reports Playwright success and an outstanding browser-health process (old session ID 1598, which may no longer be usable). This handoff records the completed work and the remaining check without assuming that unfinished process succeeded.
