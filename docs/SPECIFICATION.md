# Kiez-py specification

Status: initial specification, before implementation  
Date: 15 September 2026

## 1. Purpose and decisions

Build Kiez-py as a clone of the existing Kiez experience, with a Python backend designed for expanding AI functionality. Preserve the frontend design and existing user journeys while separating application logic, spatial operations, AI providers, and background processing.

Confirmed requirements:

- Project directory and technical name: `Kiez-py`.
- Preserve Kiez's frontend and functionality, except for the changes below.
- Support Berlin only. Exclude HafenCity and all Hamburg-specific discovery, boundaries, aliases, and copy.
- Start with the four existing Berlin areas; reconsider the selection and boundaries later.
- Use PostgreSQL, with a planned path to PostGIS.
- Make speech-to-text (STT), text-to-speech (TTS), and translation independently replaceable. Review alternatives later because the current Gemini experience is too slow and expensive for the user's needs.
- Design for additional AI features and increased workload.
- Omit the original `docs/` directory and its description/video assets from the clone.
- Use Proprietor's Python engine as a structural reference. Exclude its payments, enrichment business logic, treasury, ledger, supplier, and CFO features.

This document specifies the build; it does not claim that implementation or runtime verification has occurred. The original source trees remain unchanged.

## 2. Source inspection and parity baseline

Inspected local sources:

- `~/Desktop/Kiez/app/`: pages, layout, styles, and a catch-all API route.
- `~/Desktop/Kiez/components/`: exploration, map, diary, composer, translation, and audio UI.
- `~/Desktop/Kiez/lib/`: storage, boundaries, security, AI integrations, fixtures, dates, and Chronicle jobs.
- `~/Desktop/Kiez/migrations/001_initial.sql`, configuration examples, README, and tests.
- `~/Desktop/propriator/proprietor/engine/`: FastAPI application, models, settings, provider injection, storage, tests, and `pyproject.toml`.
- Proprietor's browser UI lives in `web/`. Its `storefront/` directory is a TypeScript payment-facing server, not the frontend to reuse.

Kiez's source code is the functional baseline where older descriptions disagree. Its current code contains five areas; Kiez-py deliberately retains only the four Berlin areas. The existing Berlin demo contains 160 contributions and 16 editorial Chronicles.

Preserve the visible brand “Kiez Notes” to maintain frontend parity; use Kiez-py for repository, package, and service naming. A visible rebrand can be decided separately.

## 3. Product behavior

### 3.1 Discovery

- Public reading requires neither account nor location permission.
- Home page retains the hero, neighborhood search/list, interactive Leaflet map, selected-area preview, explanation sections, Chronicle cards, and footer.
- Initial areas, in the existing order: Graefekiez, Reuterkiez, Bergmannkiez, Schillerkiez.
- Search retains case-insensitive matching of names, districts, and aliases, including Kreuzberg and Neukölln variants.
- “Find my Kiez” requests a fresh browser location and selects the resolved area.
- Map and list selection stay synchronized. Preserve polygon colors, labels, zoom controls, OpenStreetMap attribution, and tile-failure state.
- Preserve existing Berlin polygons as illustrative prototype boundaries pending the later selection review.
- Update copy such as “Berlin & Hamburg” to Berlin, “Two cities” to Berlin-specific wording, and empty-search suggestions to supported Berlin areas.
- HafenCity routes are unavailable; its coordinates cannot authorize a contribution.
- Refresh current moments/counts every 15 seconds and on window focus, as in Kiez.

### 3.2 Diary and contributions

- Each Kiez has one shared page at `/kiez/{slug}`.
- Display only the latest visible contribution for the current Europe/Berlin calendar day.
- Determine latest by descending creation timestamp, then ID, matching the source ordering.
- Preserve every earlier contribution for that day's collective record; do not expose a public historical contribution feed.
- Show “Waiting” on days without visible contributions. Never carry yesterday's latest contribution into today.
- Retain nickname, original text, source language, time, demo label, translation/listening controls, and report action.
- Composer retains location check, nickname, text entry, recording, editable transcription, source-language selection, character count, privacy copy, and explicit publication.
- Nickname: trimmed, 1–32 characters. Body: trimmed, 1–2,000 characters.
- Source languages: English, German, Turkish, Arabic, Spanish, mixed, unknown.
- Preserve a text draft in browser session storage and remember nickname through an anonymous server session.
- Failed or expired-location submissions preserve the draft.
- Publishing requires a valid location token bound to the session and resolved Kiez. If browsing another Kiez, explain the actual destination and navigate there after publication.
- Use a client-generated UUID idempotency key scoped to the session. Retries produce one contribution, including concurrent requests and retries after a lost response.
- Preserve the honeypot field and rejection of more than three HTTP(S) links.

### 3.3 Location and presence

- Validate latitude, longitude, and reported accuracy server-side.
- Initial resolver reproduces Kiez's polygon membership and conservative distance-to-boundary check.
- Reject coordinates outside supported areas; reject accuracy above 250 metres or uncertainty reaching beyond the permitted boundary distance.
- Incoming accuracy must be positive and at most 50,000 metres.
- Location tokens expire after five minutes. They cannot authorize a different session or arbitrary destination.
- Keep browser geolocation as lightweight presence verification. It is not proof against spoofing.
- Do not persist precise visitor coordinates for this feature.
- Put resolution behind a `LocationResolver` interface to allow PostGIS replacement without changing the composer/API contract.

### 3.4 Speech, translation, and listening

- Record up to 60 seconds, allow stop/cancel, release microphone tracks, and cancel obsolete frontend requests.
- Accept the existing upload formats: WebM, MP4, Ogg, WAV; maximum file size 4 MB, with bounded multipart request size. Preserve the source's maximum submitted duration of 61 seconds as transport tolerance.
- Transcribe in the original language/script and preserve code-switching. Never automatically publish a transcript.
- Show transcription for editing before publication; silence or unusable speech produces a clear error.
- Translate or read the currently readable contribution or a published Chronicle in an enabled language.
- Retain original text alongside labeled translations, including Arabic right-to-left display.
- Preserve stop, cancel, play-ready, autoplay-blocked fallback, and playback errors.
- A newer contribution or changed moderation status invalidates access to an older contribution, including after a slow provider request finishes.
- Core reading and text posting work without AI credentials. AI failures must never fabricate a successful output.
- Initial compatibility adapters may retain the current Google language/voice integrations and OpenAI speech fallback. No provider is a permanent architectural dependency.
- Current fallback semantics: auto uses Gemini TTS first and OpenAI only on Gemini HTTP 429 when configured; explicit provider selection remains supported.
- Same-language listening can use TTS without a translation call.

### 3.5 Chronicles and archive

- Preserve archive list and detail routes: `/kiez/{slug}/archive` and `/kiez/{slug}/archive/{date}`.
- Days follow Europe/Berlin midnight, including daylight-saving changes. Store event timestamps in UTC.
- Generate only for closed days with eligible visible contributions; empty days get no invented story.
- Preserve the three-stage pipeline: extraction, English first-person neighborhood narrative, independent review.
- “I” is the neighborhood. Preserve contrasting moods and uncertainty; avoid invented chronology, causality, consensus, facts, or identifying details.
- All eligible sources must be represented. Validate output structure, per-source coverage, and the four review flags: grounding, all sources represented, first-person neighborhood, conflicting moods preserved.
- Treat source text/audio as untrusted data rather than instructions.
- Initial implementation retains existing prompts and configurable Chronicle model, behind a replaceable pipeline. Narrative quality improvements are a later workstream.
- Store source IDs, contribution count, coverage, provider/model metadata, prompt version, generation/publication times, and status.
- Preserve pending, generating, published, failed, and review states and their existing UI messages. Unpublished body/title/source IDs must not leak through public responses.
- Archive sorts newest first and retains previous/next day navigation. A valid date without a Chronicle shows the quiet-day state; invalid routes show the existing not-found treatment.
- Published Chronicles stay stable. Provider failures retain sources and allow retry. Preserve the initial explicit oversized-day guard rather than silently omitting sources.

### 3.6 Moderation

- Anonymous users can report the current readable contribution once per session.
- Preserve authenticated internal report-list and remove operations; no admin dashboard is required.
- Removal hides the contribution and places every affected Chronicle under review.
- Publication must atomically verify claim ownership and source visibility so a removal during generation cannot publish stale content.
- Review-state Chronicles do not automatically republish through ordinary failure retries. A future review workflow is separate scope.

## 4. Frontend parity

Retain Next.js, React, TypeScript, Tailwind CSS, Radix primitives, Lucide icons, and Leaflet. Reuse the existing components and styles rather than recreating the design in Python templates.

Preserve paper/cream backgrounds, green and terracotta accents, Georgia headings, sans-serif controls, spacing, borders, icons, breakpoints, text wrapping, and interactions. Preserve loading/error/not-found states, focus indicators, skip link, dialog keyboard behavior, and reduced-motion support.

Next.js remains responsible for rendering and navigation. Python owns application rules, persistence, presence verification, moderation, and AI execution. Server-rendered pages call Python instead of importing TypeScript database functions.

Use one browser-facing origin. Route `/api/*` to Python through the development/deployment proxy. Forward cookies and origin information correctly; configure trusted proxy handling explicitly. Do not maintain a second implementation of business rules in Next.js.

Visual acceptance uses the same fixed fixture date, viewport, and deterministic map tiles for source and clone. Expected differences are Berlin-only copy/data. Dynamic dates and external tiles must not obscure actual regressions.

## 5. Backend architecture

### 5.1 Approach

Use a modular Python application with separately runnable API and worker processes. Proposed foundation: FastAPI, Pydantic/settings, PostgreSQL, SQLAlchemy with a PostgreSQL driver, versioned Alembic migrations, HTTPX/provider SDK adapters, and pytest. Select and lock exact compatible dependencies during implementation.

Borrow Proprietor's small application entry point, typed models, environment settings, lazy provider construction, injectable dependencies, and offline provider fakes. Its SQLite enrichment cache and payment architecture are not Kiez's persistence or execution model.

### 5.2 Module boundaries

- **Neighborhoods:** catalog, GeoJSON, aliases, activation, boundary versions, presence resolution.
- **Contributions:** validation, publication, latest queries, idempotency, daily membership.
- **Chronicles:** source selection, narrative workflow, archive, review/publication rules.
- **Moderation:** reports, removals, dependent-publication invalidation.
- **Sessions/security:** cookies, location signatures, authorization, rate limits.
- **AI:** feature interfaces, provider adapters, orchestration, capability reporting, usage metadata.
- **Jobs:** durable tasks, leases, retries, concurrency limits, cancellation/expiry.
- **Persistence:** repositories, transactions, migrations, connection lifecycle.

Routes perform transport parsing and invoke application services. Services enforce rules. Repositories own database access. Provider adapters handle remote API specifics. Workers invoke the same services as the API.

### 5.3 Proposed layout

```text
Kiez-py/
  docs/
    SPECIFICATION.md
    HANDOFF.md
  README.md
  compose.yaml
  .env.example
  frontend/
    app/
    components/
    lib/                 # API client, presentation utilities and types
    package.json
    package-lock.json
    tests/e2e/
  engine/
    pyproject.toml
    uv.lock
    README.md
    app/
      main.py
      settings.py
      api/               # routes, transport schemas, dependencies
      neighborhoods/
      contributions/
      chronicles/
      moderation/
      security/
      ai/
        interfaces.py
        providers/
        workflows/
      jobs/
      db/
    migrations/
    data/                # curated catalog and fictional fixtures
    tests/
      unit/
      integration/
      contract/
    scripts/
```

These are proposed module boundaries, not a requirement for a class or package per trivial operation. Avoid a single growing AI utility file.

## 6. AI extensibility and workload management

Define separate interfaces for transcription, language detection, translation, speech synthesis, and Chronicle generation. A feature may use a different provider/model from every other feature.

Each adapter declares supported languages/formats and returns a typed result with safe operational metadata. Keep provider configuration and credentials server-side. Capabilities must distinguish individual features; retain the existing `available` and `languages` fields while adding per-feature availability for the frontend.

Record operation, provider/model, duration, outcome, retry count, and available usage/cost estimates. Missing usage data is unknown, not zero. Do not log raw recordings, private credentials, location tokens, or full contribution text by default.

Long-running AI tasks run in durable workers. PostgreSQL-backed jobs are the proposed initial queue, avoiding a new broker for the first build. Workers claim jobs atomically, use expiring leases/heartbeats, and fence completion with a claim token. A replaceable queue interface allows a dedicated broker later if measured load warrants it.

Requirements:

- Separate concurrency limits and timeouts by feature/provider so Chronicle processing cannot exhaust interactive speech capacity.
- Bounded retry with backoff for transient failures; honor provider retry information. Do not repeatedly retry invalid inputs or configuration failures.
- Configurable per-session/global limits and AI workload budgets.
- Idempotent task creation and publication; assume delivery can repeat.
- User cancellation stops polling and discards stale results; remote cancellation is best effort where supported.
- Scheduler enqueues closed-day work and catches up missed days. No browser request is responsible for completing a multi-minute Chronicle.
- Interactive endpoints may briefly await a worker result for compatibility; otherwise return an accepted task and let the frontend poll behind its existing progress state.
- No durable raw-audio retention. A queued transcription may use short-lived private staging with deletion after completion, cancellation, or expiry and a cleanup process for crashes.
- Translation/audio caching is optional and bounded: key by source content/version, language, provider/model, and settings. Recheck source readability before returning cached or completed output; moderation invalidates it. Define retention explicitly before enabling persistent caches.

A future AI feature should add its own schemas/workflow, provider capability, jobs if needed, and tests without changing contribution publication or neighborhood resolution.

### Later provider evaluation

Compare candidate services or local models using a shared sample set in English, German, Turkish, Arabic, Spanish, and mixed speech. Measure typical and tail latency, total cost per task, transcription accuracy, translation fidelity, voice quality, failure rate, concurrency behavior, and operational effort. Include silence, background noise, accents, and longer Chronicles.

Do not promise an alternative is cheaper or faster before this evaluation. Streaming audio, self-hosted models, and new AI product features are later decisions; the interfaces must permit them.

## 7. PostgreSQL and neighborhood evolution

Use ordinary PostgreSQL locally and in deployment. Provide a local container configuration so no hosted account is required. Do not retain the JavaScript PGlite runtime as a Python backend dependency. Hosted PostgreSQL/Supabase may remain a deployment option using a server-only database connection.

Retain the existing core entities and constraints:

| Entity | Required content |
| --- | --- |
| Neighborhood | Stable ID/slug, name, district, aliases, description, color, center, geometry, boundary version, active status |
| Session | Anonymous ID, nickname, creation time |
| Contribution | ID, Kiez ID, body, nickname, language, input mode, UTC time, Berlin diary date, session, unique idempotency key, visibility, demo marker |
| Chronicle | Unique Kiez/date, title/body/language, sources/coverage, count, status, model/prompt metadata, timestamps, claim/error metadata, demo marker |
| Report | Contribution/session pair uniqueness and creation time |
| Rate limit | Atomic counters and expiry shared across API processes |
| Setting | Demo anchor and application metadata |
| AI job | Operation, state, references, idempotency identity, lease, attempts, availability/expiry times, safe result/error metadata |

Preserve indexes for latest-per-day, archives, unique contribution retries, and unique Chronicle days. Add indexes appropriate to runnable jobs. Use transactions for publication and moderation state changes.

Neighborhood data must have one authoritative source in PostgreSQL, populated from a versioned seed catalog. The frontend receives display data and GeoJSON through the API; it must not maintain an independent hard-coded polygon list.

Future catalog changes retain stable IDs and existing historical associations. Adding, renaming, or retiring an area must not delete its contributions. Boundary updates carry a version; short-lived presence tokens should bind that version and require rechecking if it changes. Splits/merges and historical reassignment require an explicit later policy.

### PostGIS path

PostGIS is a good planned extension for a larger or more complex neighborhood catalog. It provides indexed spatial queries, containment, and proximity operations. `ST_Covers` includes boundary points, so its semantics must be reconciled with Kiez's conservative accuracy checks rather than substituted blindly. See [PostGIS spatial indexes](https://postgis.net/documentation/faq/spatial-indexes/) and [ST_Covers](https://postgis.net/docs/manual-3.7/en/ST_Covers.html).

Initial clone: preserve the existing resolver behind its interface and store valid GeoJSON. Later migration:

1. Enable PostGIS on the selected PostgreSQL host.
2. Validate/backfill versioned Polygon/MultiPolygon data in SRID 4326 and add appropriate GiST spatial indexes.
3. Replace the resolver with database spatial queries. Use geography or an appropriate metric projection for metre-based distances; do not interpret longitude/latitude degrees as metres.
4. Preserve outside/uncertain/resolved outcomes and API shapes.
5. Compare old/new results on known interior, exterior, edge, uncertainty, overlap, and invalid-geometry cases before switching.
6. Define overlap precedence, holes, disconnected areas, and boundary inclusion during the later catalog review.

PostGIS helps spatial work. AI capacity still depends on workers, provider limits, caching decisions, budgets, and workload measurement. It is not a general solution for AI throughput.

## 8. API contracts

Keep existing browser contracts where possible, including camelCase request fields and snake_case persisted response fields. Normalize validation errors into the existing `{ "error": "..." }` envelope rather than exposing FastAPI's default validation shape.

| Method and route | Behavior |
| --- | --- |
| GET `/api/neighborhoods` | Active Berlin catalog with latest moment, today's visible count, published archive count |
| GET `/api/latest?kiez={id}` | Current visible contribution or null |
| GET `/api/session` | Establish/read anonymous session and nickname |
| GET `/api/capabilities` | Existing availability/languages plus per-feature capabilities |
| POST `/api/location` | Latitude/longitude/accuracy to neighborhood and signed token |
| POST `/api/contributions` | Existing nickname/body/language/inputMode/locationToken/idempotencyKey/website payload; returns ID and neighborhood_id |
| POST `/api/report` | Report current readable contribution by ID |
| POST `/api/transcribe` | Audio/duration multipart to transcript/language, or accepted task |
| POST `/api/translate` | kind/id/language to text/language/translated, or accepted task |
| POST `/api/speech` | Same input; compatible WAV data URI result initially, or accepted task |
| GET `/api/admin/reports` | Bearer-protected latest 100 reports |
| POST `/api/admin/remove` | Bearer-protected removal by contribution ID |
| GET or POST `/api/cron` | Bearer-protected, idempotent enqueue/catch-up trigger |
| GET `/healthz` | Process health without AI credentials |

New read contracts replace server-page database imports: neighborhood detail, archive list, and Chronicle-by-date endpoints under `/api/neighborhoods/{slug}`. They return sanitized public models and distinguish nonexistent areas from valid quiet dates. Keep latest-contribution readability rules consistent across all routes.

New `/api/jobs/{id}` polling returns pending/running/completed/failed state and the feature's existing result shape. Enforce session ownership, source visibility, and expiry. Optional cancellation uses the same ownership checks. Document these contracts in generated OpenAPI and contract tests.

The cron enqueue response intentionally changes from completed generation counters to accepted-work counters; document it for scheduler operators. UI progress labels stay familiar despite asynchronous execution.

## 9. Security and operational behavior

- Preserve signed anonymous `kiez-session` cookies: HttpOnly, SameSite=Lax, secure in production, 30-day lifetime.
- Preserve same-origin mutation checks and separate admin/cron bearer secrets. Reject missing privileged credentials.
- Enforce body/upload limits and bounded processing, including requests without Content-Length.
- Preserve initial limits: general session POST requests 60/minute, publish 4/minute, reports 5/minute, transcription 6/session/minute and 60 global/minute, translation/speech 12/session/minute and 120 global/minute. Adapt job polling separately so it does not consume publication capacity.
- AI adapters use explicit timeouts and safe errors. Text functionality remains available during provider outages.
- Public responses exclude session IDs, idempotency keys, internal errors, and unpublished narrative content.
- Browser code has no database or AI credentials. Use a server database role and preserve protection against direct public table access for hosted configurations.
- Expose readiness separately from liveness, including database connectivity. Provider outages should not mark all reading/writing unavailable.
- Measure API latency, queue depth/age, provider latency/failure/usage, and job retries. Use correlation IDs across API and worker tasks.
- Deploy API and workers independently; avoid process-local rate limits, claims, or session state.

## 10. Fixtures, setup, and migration scope

- Copy source frontend and necessary configuration; omit original docs, `.git`, local secrets, `.data`, dependency folders, build output, deployment links, and generated test artifacts.
- Start with a fresh Kiez-py database. Migration of real Kiez submissions is not part of the initial clone and must not happen implicitly.
- Port the four Berlin fixture sets faithfully: five days × four areas × eight contributions = 160 contributions; the four closed days per area yield 16 editorial Chronicles.
- Anchor fixtures once, preserve fictional labels and source languages, and make repeated seeding idempotent.
- Provide explicit demo reset that affects only demo-tagged records and preserves real records. Retain keyless reading/text operation and a demo-disabled mode.
- Provide migrations and seed commands separately from ordinary production request handling.
- Document local startup for frontend, API, worker, and PostgreSQL; provide locked dependencies and environment examples with no credentials.
- Retain applicable existing provider environment names for compatibility. Add database, internal API URL/public origin, worker/concurrency, queue, timeout, and provider-selection settings.
- Exact deployment host and later AI providers remain open. Local development and test setup must not depend on those decisions.

## 11. Verification and acceptance

### Functional and frontend

- Compare home, populated/Waiting diary, composer, archive, published Chronicle, and error/review states against Kiez using fixed fixtures.
- Check desktop, tablet, and 390×844 mobile; no horizontal overflow, accessible keyboard interaction, reduced-motion behavior, and Arabic rendering.
- Verify map/search navigation and graceful tile failure using intercepted tiles in automated tests.
- Assert only the four Berlin areas appear; Hamburg/HafenCity aliases and venue coordinates do not resolve.
- Verify location-denied, outside, uncertain, expired-token, and cross-Kiez publishing flows.
- Verify draft retention, voice review/cancel, translation, playback fallback, report action, and refreshing to a newer contribution.

### Python, database, and AI

- Port meaningful existing date, location, fixture, concurrency, Chronicle coverage, provider-error, fallback, and WAV tests to pytest.
- Use a real isolated PostgreSQL database for transactional integration tests; never a developer or hosted production database.
- Exercise concurrent idempotent submissions, latest ordering, atomic claims, expired leases, duplicate job delivery, and worker restart recovery.
- Verify removal before/during AI generation or cache retrieval prevents hidden content from being returned or published.
- Verify Europe/Berlin midnight and DST, no current-day synthesis, quiet dates, stable published Chronicles, and retries without lost sources.
- Inject fake providers for routine tests: unavailable credentials, malformed responses, 429, timeout, empty speech, unsupported language, and out-of-order UI results.
- Run frontend typecheck/build, backend tests, API contract checks, and browser tests before declaring the clone complete.
- Live multilingual voice/translation checks are separate, credential-dependent validation. Record actual latency and cost observations; do not present mocked tests as provider-quality evidence.

## 12. Implementation sequence

1. Establish frontend parity baseline and extract Berlin-only catalog/fixtures.
2. Scaffold Python modules, PostgreSQL migrations, configuration, API contracts, and local services.
3. Implement sessions, location, contributions, public page reads, and moderation; connect the retained frontend.
4. Implement provider interfaces, compatibility adapters, durable jobs/workers, and Chronicle workflow.
5. Verify full user journeys, visual parity, failure recovery, concurrency, and operational setup.
6. Later: revise Berlin Kiez selection and boundaries; evaluate/introduce PostGIS.
7. Later: benchmark and replace speech/translation providers, improve Chronicle quality, and add new AI features through the module/job interfaces.

The initial build is complete when the existing experience works with the Python backend, Berlin-only adjustments are verified, core operations survive provider failures, and AI work can run independently from the web process. Future catalog and provider decisions must not require replacing that foundation.
