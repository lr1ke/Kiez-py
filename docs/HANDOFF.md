# Kiez-py — first implementation status

Updated: 16 September 2026  
Basis: [initial specification](SPECIFICATION.md), dated 15 September 2026. Implementation took place on 15 September; the final browser runtime check was completed on 16 September.

## Overall status

The first implementation attempt produced a working local Berlin-only Kiez Notes application with the retained Next.js/React frontend, a modular Python API, PostgreSQL persistence, and a separately running AI worker. The recorded backend, frontend build, and browser checks passed. Reading and text publication work without hosted accounts or AI credentials.

This is the initial implementation baseline for review against the specification. Automated verification and a limited visual comparison are complete; exhaustive frontend acceptance, live AI quality, and deployment validation remain open. The results below do not establish full acceptance of every requirement in specification section 11.

## Implementation against the specification

| Specification area | First implementation result |
| --- | --- |
| Scope and frontend (§1–4) | Retained the Kiez Notes brand, pages, components, styles, map, diary, composer, archive, translation and listening controls. Restricted discovery and location resolution to Graefekiez, Reuterkiez, Bergmannkiez and Schillerkiez; Hamburg/HafenCity excluded. |
| Contributions and presence (§3.2–3.3) | Signed anonymous sessions and short-lived location tokens, location/boundary checks, session-scoped idempotent publication, latest visible contribution per Berlin day, retained historical sources, draft recovery and cross-Kiez posting. |
| Speech and language features (§3.4, §6) | Separate transcription, detection, translation and speech interfaces; Gemini/OpenAI compatibility adapters; editable transcript review, asynchronous polling/cancellation, Arabic direction handling and keyless feature availability. Live provider behavior remains to be evaluated. |
| Chronicles and moderation (§3.5–3.6) | Three-stage extraction/narrative/review workflow, source coverage gates, archive/status handling, reports/removal, and publication checks for source visibility and worker ownership. |
| Python architecture and API (§5, §8–9) | Modular FastAPI application, typed contracts, server-side validation, same-origin API proxy, rate limits, privileged admin/cron endpoints, liveness/readiness and operational metrics. Next.js uses Python for application data and rules. |
| Durable AI execution (§6) | PostgreSQL queue and independent workers, interactive/Chronicle concurrency lanes, leases and heartbeats, ownership fencing, bounded retries, idempotent task creation, cancellation, expiry, task budgets, temporary audio cleanup and closed-day scheduling. |
| Database and catalog (§7) | PostgreSQL persistence, versioned migrations and one authoritative neighborhood catalog shared by map and location resolution. Existing illustrative polygons retained behind a replaceable resolver; PostGIS deferred. |
| Fixtures and local setup (§10) | Four-area catalog, 160 fictional contributions in five languages and 16 editorial Chronicles; stable demo anchor, idempotent seeding and explicit demo reset preserving real contributions. Local launcher, environment examples, locked dependencies, Dockerfiles and Compose configuration provided. |

The original frontend stylesheet was confirmed unchanged. A bounded featured-Chronicle endpoint retrieves at most three public home-page cards in one query. AI request idempotency keys are scoped to operation and session, including transcription.

## Verification results

The 15 September results were recovered from the implementation session and recorded in the original handoff. They were not rerun solely for this status rewrite. The runtime/hydration result was directly verified on 16 September.

| Check | Result | Date |
| --- | --- | --- |
| Backend pytest, including real isolated PostgreSQL integration tests | 53 passed in 2.19s; no skips reported | 15 September |
| Ruff | All checks passed | 15 September |
| Frontend standalone TypeScript check | Passed | 15 September |
| Frontend production build | Passed, including compilation, type checking and page generation | 15 September |
| Playwright user journeys | 8 passed in 21.6s | 15 September |
| Shared-style comparison with original Kiez | Shared desktop typography, colors, spacing and borders matched; desktop/mobile screenshots captured | 15 September |
| Browser runtime and hydration check | Passed with zero errors on mobile home, diary, archive and composer dismissal | 16 September |

Backend coverage includes sessions, location and boundary versions, concurrent idempotency, moderation/generation races, fixture reset, Berlin midnight/DST, provider errors and fallback, WAV output, queue ownership/cancellation/expiry, budget/lane isolation, scheduling and stale-worker publication prevention.

The eight browser scenarios cover discovery/archive/keyless AI errors; location-gated publication and idempotency; mobile overflow and keyboard composer; Berlin-only search and location rejection; draft recovery after failed publication; cross-Kiez routing and retained draft; mocked Arabic translation/cancellation; and simulated microphone recording with editable transcript before publication.

The visual comparison checked shared computed styles, not every page and interaction state. Its parity screenshots were no longer present after the final Playwright run. Fake providers and browser mocks demonstrate application behavior, not live multilingual model quality.

## Remaining acceptance work and limitations

- Complete the frontend acceptance review in specification §11, including tablet layouts, reduced motion and all required visual/error/review states. Existing browser coverage is useful but not exhaustive.
- Run credentialed multilingual speech, translation and Chronicle rehearsals. Model access, output quality, latency, cost and live failure behavior have not been established.
- Validate Docker startup and the eventual production deployment. Configuration exists; successful deployment is not claimed.
- Investigate any recurring local frontend stall. On 16 September the existing frontend accepted a listener but did not respond to HTTP requests. Restarting the app restored service and the browser check passed; the underlying cause was not determined.
- Interactive job results expire after 15 minutes. There is no reusable translation/audio cache. Task budgets count tasks, not monetary cost; external provider billing is not exactly-once. Audio retention in database backups/WAL remains an infrastructure concern.

## Deferred workstreams

As agreed in the specification, these remain separate from the initial clone:

- Review Berlin neighborhood selection and replace illustrative boundaries where appropriate.
- Evaluate and introduce PostGIS if the catalog and spatial requirements warrant it.
- Benchmark alternative speech/translation providers or local models before choosing replacements.
- Improve Chronicle narrative quality and add further AI features through the existing interfaces and job system.

## Project map and local operation

- `frontend/`: retained UI, Python API proxy, server read client and browser tests.
- `engine/app/`: API, security, neighborhoods, contributions, moderation, AI, Chronicles, jobs and persistence.
- `engine/migrations/`: initial schema and provider-metadata migrations.
- `engine/data/`: Berlin catalog and fictional fixtures.
- `scripts/dev.py`: migration/seed and local API, worker and frontend launcher.
- [Root README](../README.md): setup, configuration and verification commands.
- [Engine README](../engine/README.md): execution guarantees, retention and operational limits.

At the last check on 16 September, the app was running at **http://localhost:3001**, with API on **127.0.0.1:8000**, PostgreSQL on **127.0.0.1:55432**, and a separate worker. The API readiness check passed before restart; the launcher confirmed all app processes started afterward. Runtime availability should be checked again when resuming work.

The dedicated PostgreSQL 17 cluster is stored in `.data/postgres`; existing local configuration is in the ignored `engine/.env`. Preserve both. From the project root, start PostgreSQL if stopped:

```sh
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D "$PWD/.data/postgres" -l "$PWD/.data/postgres.log" -o '-p 55432 -h 127.0.0.1 -k /private/tmp' start
```

Start the app if stopped:

```sh
python3 scripts/dev.py
```

Check existing listeners before launching duplicate processes. Startup seeding is idempotent; do not reset fixtures merely to clean up test submissions. A Graefekiez location rehearsal uses latitude **52.4917**, longitude **13.4150**, accuracy **10**.

For further validation, use the README commands. Backend integration tests require an explicit `TEST_DATABASE_URL` pointing to a dedicated database whose name ends in `_test`; without it, integration tests skip. Browser tests publish test contributions into the running instance, so use a dedicated instance when real visitor data matters.

The next project decision is which remaining acceptance item or deferred workstream to address. There is no outstanding check left over from the interrupted implementation session.
