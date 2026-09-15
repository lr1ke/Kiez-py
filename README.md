# Kiez-py

Kiez Notes with the existing React/Next.js frontend and a modular Python backend. Explore four Berlin Kieze, leave a location-checked note, and read the neighborhood's daily Chronicle.

The clone keeps Kiez's design and interaction flow. HafenCity/Hamburg are excluded. PostgreSQL owns the neighborhood catalog, contributions, sessions, moderation and durable AI work. API and worker processes scale independently. Speech recognition, translation, speech synthesis and Chronicle generation have separate provider interfaces.

## Run locally

Requires Python 3.11+, Node.js 22+, PostgreSQL 17, and uv. No hosted account or AI credentials are required for reading and text contributions.

```sh
cd engine
cp .env.example .env
uv sync --extra dev --frozen
cd ../frontend
npm ci
cd ..
```

Set `engine/.env`'s `DATABASE_URL` to a dedicated PostgreSQL database. If Docker is installed, `docker compose up -d postgres` supplies the example database. Keep `PUBLIC_ORIGIN=http://localhost:3001` for the default frontend port.

```sh
python3 scripts/dev.py
```

Open **http://localhost:3001**. The launcher applies migrations, seeds the demo idempotently, and starts the Python API (8000), worker and frontend (3001). Ctrl+C stops those three processes; PostgreSQL remains running.

**This workspace:** a separate local PostgreSQL cluster was installed/initialized at `.data/postgres`, listening only on `127.0.0.1:55432`. Its local connection is already set in the ignored `engine/.env`. After a restart, start it with:

```sh
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D "$PWD/.data/postgres" -l "$PWD/.data/postgres.log" -o '-p 55432 -h 127.0.0.1 -k /private/tmp' start
```

This local-only cluster uses trust authentication on loopback; it is a development setup. The Compose example uses its own password-protected PostgreSQL instance and persistent volume.

## Docker Compose alternative

Copy `engine/.env.example` to `engine/.env`, then:

```sh
docker compose up --build
```

This launches PostgreSQL, a one-time migration/seed service, API, worker and frontend. The browser URL is still `http://localhost:3001`. The example is for local use; production requires HTTPS, independent session/admin/cron secrets, a protected database and a configured public origin. Set `ENVIRONMENT=production` only with a strong `SESSION_SECRET` and HTTPS. API traffic should use one trusted browser-facing origin.

## Features and provider settings

- Four initial Kieze: Graefekiez, Reuterkiez, Bergmannkiez, Schillerkiez.
- Anonymous nickname sessions; fresh browser location required only for posting.
- One current note per Berlin day; previous contributions retained for Chronicles.
- Text or reviewed voice transcription, five-language translation/listening, report controls, and archives.
- Three-stage Chronicle generation with source coverage and review gates.
- Durable jobs, cancellation, expiring claims, bounded retries, separate interactive/Chronicle capacity, and operational metrics.

Add provider keys to `engine/.env` and restart API/worker to enable AI. Original Gemini and OpenAI adapters are included for compatibility. Their later replacement and a Berlin boundary/catalog revision are planned in [SPECIFICATION.md](docs/SPECIFICATION.md). PostGIS is not required or enabled yet.

The composer accepts original-language transcripts only after review. Browser microphone and geolocation require localhost or HTTPS. Voice recording is tested in Chrome. No audio is automatically published. Workers temporarily stage uploads and expire job outputs; see [engine details](engine/README.md) for retention and execution guarantees.

For an away-from-Berlin rehearsal use Chrome Sensors with **52.4917, 13.4150**, accuracy 10, for Graefekiez. Existing polygons are illustrative, not official boundaries. Tiles retain OpenStreetMap attribution and normal browser caching.

## Data and fixtures

A fresh seed creates four areas, 160 fictional contributions in five languages, and 16 editorial Chronicles. The demo anchor is retained across restarts. Empty future days show Waiting. Raw source project databases, secrets, deployment state and original docs/video are not copied.

```sh
cd engine
uv run python -m app.db.seed 2026-09-15 --reset-demo
```

This explicitly replaces demo-tagged records and preserves real contributions. Stop API/workers before resetting fixtures. `DEMO_DATA=false` disables demo seeding for a fresh database. Catalog seeds insert missing areas and do not overwrite curated records on startup. Neighborhoods and map GeoJSON come from the same database; historical IDs remain stable for future catalog changes.

## Verification

Backend tests use fake providers and an isolated PostgreSQL database whose name must end in `_test`. Every integration test gets its own temporary schema. They never use the demo database as a fallback.

```sh
# Create a separate test database on your PostgreSQL server first.
cd engine
TEST_DATABASE_URL=postgresql+psycopg://kiez:kiez@127.0.0.1:5432/kiez_test uv run pytest -q
uv run ruff check app tests
cd ../frontend
npm run typecheck
npm run build
npm run test:e2e
```

Without `TEST_DATABASE_URL`, database tests are explicitly skipped; this is not a full verification run. Browser tests use Chrome, stub external map tiles, simulate location/audio devices, and mark their text submissions as test visitors. They exercise a running clone on port 3001; use a dedicated test instance when real visitors' data is present.

Unit/integration tests cover source coverage, moderation races, worker lease recovery, retry/idempotency, cookie/location validation, DST, fixture reset, provider failures and WAV output. Live AI language quality, model access, latency and cost require credentials and a separate evaluation.

## Repository map

- `frontend/`: retained pages/styles/components; same-origin API proxy and server read client.
- `engine/app/`: modular Python features, providers, queue and workers.
- `engine/migrations/`: versioned PostgreSQL schema.
- `engine/data/`: original Berlin fixture content and initial neighborhood catalog.
- `engine/tests/`, `frontend/tests/`: automated checks.
- `scripts/dev.py`: local process launcher.
- `docs/SPECIFICATION.md`: agreed scope and future extension points.
- `docs/HANDOFF.md`: implementation status, verification results, and resume instructions.

Technical project name: **Kiez-py**. Visible product brand: **Kiez Notes**.
