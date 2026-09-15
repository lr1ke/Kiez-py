# Kiez-py engine

Python API and PostgreSQL-backed AI workers. See the [root README](../README.md) for startup.

## Boundaries

`api/` handles HTTP; feature services enforce rules; `db/` owns transactions and fixtures. `ai/interfaces.py` defines independent transcription, translation, detection, speech and narrative capabilities. `ai/providers/` contains remote adapters. `jobs/queue.py` provides durable work claims; `jobs/worker.py` executes operations. `chronicles/jobs.py` coordinates publication with source visibility and worker ownership.

Add a provider by implementing its feature protocol, registering it in `ai/registry.py`, adding settings/capabilities, and testing it with HTTPX fake responses. Add a workflow in `ai/workflows/` and a worker operation when durable execution is needed. Do not add provider calls to frontend code or contribution transactions.

The initial adapters retain Kiez's models for compatibility. They are not a recommendation that those models are currently optimal or available to every account.

## Commands

```sh
uv sync --extra dev --frozen
uv run alembic upgrade head
uv run python -m app.db.seed
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
# Another terminal:
uv run python -m app.jobs.worker
```

No API key is needed to start either process. Workers schedule Chronicles only when their configured capability is available. Authenticated `/api/cron` can explicitly enqueue catch-up work. The schedule is idempotent across workers.

## Worker guarantees and limits

- Lane concurrency is enforced across processes sharing a database: interactive default 4, Chronicle default 1.
- Claims expire after 120 seconds and renew every third of that period. A lost claim cannot complete or publish.
- Transient failures retry up to three attempts with backoff and Retry-After handling. Failed Chronicle days may be re-enqueued after a five-minute cooldown; review states never auto-republish.
- A configured daily task budget counts accepted tasks, not dollars. Provider call usage is recorded when supplied; monetary estimates are not invented. Chronicle tasks may invoke three calls per attempt.
- All AI outputs are short-lived job results; interactive results expire after 15 minutes. There is no reusable translation/audio cache yet.
- Recordings are temporarily staged in a private database table for cross-process transcription. They are deleted on completion/cancellation/terminal failure and periodically swept on expiry. Database backup/WAL retention is an infrastructure setting; do not include staging data in retained backups if immediate removal is required.
- Original text is never copied into durable language-task payloads; tasks reference readable content IDs. Completed outputs are rechecked for visibility on retrieval.
- Detection runs after publication so a language provider cannot delay a text contribution. Unknown language may change on the next refresh.
- Repeated delivery is expected. The database provides idempotency and publication fencing, not a claim of exactly-once external provider billing.

## Operations

`/healthz` is keyless process liveness. `/readyz` checks database/migration readiness. `/api/admin/metrics` requires `ADMIN_SECRET` and summarizes queue depth/age and provider calls/latency/failures over the last day. Structured logs link HTTP and worker activity with correlation IDs; credentials and source content are omitted.

Configure all worker processes with the same lane limits and secrets. Run migrations as a release step, then seed explicitly if desired; request startup performs neither. For a hosted database use a dedicated server role, protect connection credentials, and keep direct public table access disabled. Schema tables enable row-level security without browser policies; the owner performs server-side access.

PostGIS is deliberately deferred. Replace `GeoJSONResolver` with a `LocationResolver` implementation and a schema migration after the Berlin boundary review.

## Provider contract references

The compatibility adapters follow the source application and were checked against official documentation:

- [OpenAI Responses](https://developers.openai.com/api/reference/resources/responses/methods/create)
- [OpenAI speech](https://developers.openai.com/api/reference/resources/audio/subresources/speech/methods/create)
- [Gemini audio understanding](https://ai.google.dev/gemini-api/docs/audio)
- [Gemini speech generation](https://ai.google.dev/gemini-api/docs/speech-generation)

Routine tests use injected fakes. Live provider quality, availability, latency and cost need a separate credentialed rehearsal.

AI POST endpoints accept an optional UUID `Idempotency-Key` header. Keys are scoped to operation and session; repeated submissions return the same job. The frontend sends a new key for each intentional request. `/api/featured-chronicles` returns at most three public cards through one database query, avoiding a growing set of per-neighborhood archive requests.
