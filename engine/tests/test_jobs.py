import asyncio
import uuid

import pytest

from app.chronicles.jobs import generate, schedule
from app.errors import AppError
from app.jobs.queue import PostgresQueue
from app.jobs.worker import process
from app.moderation.service import remove
from tests.test_ai import FakeProvider
from tests.test_api import post_note


async def test_atomic_claims_leases_and_duplicate_completion(db, settings):
    settings.interactive_concurrency = 1
    q = PostgresQueue(db, settings)
    job_id = await q.enqueue("detect", {"id": "absent"}, dedupe="same")
    assert await q.enqueue("detect", {"id": "absent"}, dedupe="same") == job_id
    claimed = await asyncio.gather(q.claim("interactive"), q.claim("interactive"))
    assert sum(x is not None for x in claimed) == 1
    first = next(x for x in claimed if x)
    await db.execute("UPDATE ai_jobs SET lease_until=now()-interval '1 second' WHERE id=:id", id=job_id)
    second = await q.claim("interactive")
    assert second["attempts"] == 2 and second["claim_token"] != first["claim_token"]
    assert not await q.complete(first, {"stale": True})
    assert await q.complete(second, {"ok": True})
    assert not await q.complete(second, {"twice": True})


async def test_queue_ownership_cancel_expiry_and_audio_cleanup(db, settings):
    q = PostgresQueue(db, settings)
    await db.execute("INSERT INTO sessions(id) VALUES ('one'),('two')")
    job_id = await q.enqueue("transcribe", {"mime_type": "audio/webm"}, "one", audio=b"private recording")
    with pytest.raises(AppError) as error:
        await q.poll(job_id, "two")
    assert error.value.status == 404
    await q.cancel(job_id, "one")
    assert not await db.one("SELECT job_id FROM audio_staging WHERE job_id=:id", id=job_id)
    assert (await q.poll(job_id, "one"))["status"] == "cancelled"
    expired = await q.enqueue("transcribe", {"mime_type": "audio/webm"}, "one", audio=b"expiring")
    await db.execute("UPDATE ai_jobs SET expires_at=now()-interval '1 second' WHERE id=:id", id=expired)
    await q.cleanup()
    assert not await db.one("SELECT job_id FROM audio_staging WHERE job_id=:id", id=expired)
    with pytest.raises(AppError) as error:
        await q.poll(expired, "one")
    assert error.value.status == 410


async def test_retry_is_bounded_and_respects_retry_after(db, settings):
    settings.job_max_attempts = 2
    q = PostgresQueue(db, settings)
    job_id = await q.enqueue("detect", {"id": "unused"})
    first = await q.claim("interactive")
    await q.fail(first, AppError(429, "Quota", retryable=True, retry_after=60))
    assert await q.claim("interactive") is None
    await db.execute("UPDATE ai_jobs SET available_at=now()-interval '1 second' WHERE id=:id", id=job_id)
    second = await q.claim("interactive")
    await q.fail(second, AppError(502, "Temporary", retryable=True))
    assert (await db.one("SELECT status FROM ai_jobs WHERE id=:id", id=job_id))["status"] == "failed"
    assert await q.claim("interactive") is None


async def test_interactive_jobs_end_to_end_and_visibility(client, db, settings):
    response, _ = await post_note(client)
    entry_id = response.json()["id"]
    q = PostgresQueue(db, settings)
    settings.gemini_api_key = "test-only"
    task = await client.post(
        "/api/translate", json={"kind": "contribution", "id": entry_id, "language": "de"}
    )
    assert task.status_code == 202, task.text
    job = await q.claim("interactive")
    await process(q, FakeProvider().providers(), job)
    result = await client.get("/api/jobs/" + task.json()["jobId"])
    assert result.json()["result"]["text"] == "Ein leiser Regentag."
    await post_note(client, body="New current note.")
    assert (await client.get("/api/jobs/" + task.json()["jobId"])).status_code == 404


async def test_transcription_upload_job_and_delete(client, db, settings):
    settings.gemini_api_key = "fake"
    response = await client.post(
        "/api/transcribe",
        files={"audio": ("moment.webm", b"fake audio", "audio/webm")},
        data={"duration": "2"},
    )
    assert response.status_code == 202, response.text
    q = PostgresQueue(db, settings)
    job = await q.claim("interactive")
    await process(q, FakeProvider().providers(), job)
    result = (await client.get("/api/jobs/" + response.json()["jobId"])).json()
    assert result["result"]["language"] == "de"
    assert not await db.one("SELECT * FROM audio_staging")


async def add_closed_note(db):
    await db.execute("""INSERT INTO contributions(id,neighborhood_id,nickname,body,language,input_mode,diary_date,idempotency_key)
        VALUES ('closed','graefekiez','Test','I heard rain and bells.','en','text','2026-01-01','closed')""")


async def test_chronicle_scheduler_generation_and_stability(db, settings):
    await add_closed_note(db)
    assert (await schedule(db, settings))["enqueued"] == 1
    assert (await schedule(db, settings))["enqueued"] == 0
    q = PostgresQueue(db, settings)
    job = await q.claim("chronicle")
    fake = FakeProvider()
    await process(q, fake.providers(), job)
    c = await db.one("SELECT * FROM chronicles WHERE id='graefekiez:2026-01-01'")
    assert c["status"] == "published" and c["source_ids"] == ["closed"]
    assert len(fake.calls) == 3
    assert (await schedule(db, settings))["enqueued"] == 0
    assert (await db.one("SELECT status FROM ai_jobs WHERE id=:id", id=job["id"]))["status"] == "completed"
    await remove(db, "closed")
    assert (await db.one("SELECT status FROM chronicles WHERE id=:id", id=c["id"]))["status"] == "review"
    assert (await schedule(db, settings))["enqueued"] == 0


async def test_removal_during_generation_prevents_publication(db, settings):
    await add_closed_note(db)
    await schedule(db, settings)
    q = PostgresQueue(db, settings)
    job = await q.claim("chronicle")
    fake = FakeProvider()

    async def remove_source():
        await remove(db, "closed")

    fake.before_review = remove_source
    await process(q, fake.providers(), job)
    c = await db.one("SELECT status,body FROM chronicles WHERE id='graefekiez:2026-01-01'")
    assert c["status"] == "failed" and not c["body"]


async def test_expired_worker_cannot_take_new_workers_chronicle(db, settings):
    await add_closed_note(db)
    await schedule(db, settings)
    q = PostgresQueue(db, settings)
    old = await q.claim("chronicle")
    await db.execute("UPDATE ai_jobs SET lease_until=now()-interval '1 second' WHERE id=:id", id=old["id"])
    new = await q.claim("chronicle")
    with pytest.raises(AppError):
        await generate(db, settings, FakeProvider().providers(), old)
    assert (await db.one("SELECT status FROM chronicles"))["status"] == "pending"
    await process(q, FakeProvider().providers(), new)
    assert (await db.one("SELECT status FROM chronicles"))["status"] == "published"


async def test_budget_and_lane_isolation(db, settings):
    settings.ai_daily_task_limit = 2
    settings.interactive_concurrency = 1
    q = PostgresQueue(db, settings)
    await q.enqueue("detect", {"id": "a"})
    await q.enqueue("chronicle", {"id": "b"})
    with pytest.raises(AppError) as error:
        await q.enqueue("detect", {"id": "c"})
    assert error.value.status == 429
    assert await q.claim("interactive")
    assert await q.claim("chronicle")


async def test_ai_http_idempotency(client, db, settings):
    settings.gemini_api_key = "fake"
    headers = {"idempotency-key": str(uuid.uuid4())}

    async def submit():
        return await client.post(
            "/api/transcribe",
            files={"audio": ("test.webm", b"audio", "audio/webm")},
            data={"duration": "2"},
            headers=headers,
        )

    first, second = await submit(), await submit()
    assert first.status_code == second.status_code == 202
    assert first.json()["jobId"] == second.json()["jobId"]
    assert (await db.one("SELECT count(*) AS count FROM ai_jobs"))["count"] == 1
    assert (await db.one("SELECT count(*) AS count FROM audio_staging"))["count"] == 1
