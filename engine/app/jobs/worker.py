"""Run `python -m app.jobs.worker`; API and workers share no in-memory state."""

import asyncio
import base64
import contextlib
import json
import logging
import signal
import time

import httpx

from app.ai.providers.transport import job_context
from app.ai.registry import build_providers, capabilities
from app.chronicles.jobs import generate, schedule
from app.contributions.service import readable
from app.db.database import Database
from app.errors import AppError
from app.jobs.queue import PostgresQueue
from app.settings import get_settings

logger = logging.getLogger("kiez.worker")


async def execute(db, settings, providers, job):
    operation, payload = job["operation"], job["payload"]
    if operation == "chronicle":
        return await generate(db, settings, providers, job)
    if operation == "transcribe":
        blob = await db.one(
            "SELECT data FROM audio_staging WHERE job_id=:id AND expires_at>now()", id=job["id"]
        )
        if not blob:
            raise AppError(410, "Recording expired. Please record again.")
        return (
            await providers.transcriber.transcribe(bytes(blob["data"]), payload["mime_type"])
        ).model_dump()
    if operation == "detect":
        entry = await db.one(
            "SELECT body FROM contributions WHERE id=:id AND visibility='visible' AND language='und'",
            id=payload["id"],
        )
        if entry:
            language = await providers.detector.detect(entry["body"])
            await db.execute(
                "UPDATE contributions SET language=:language WHERE id=:id AND language='und' AND visibility='visible'",
                language=language,
                id=payload["id"],
            )
        return {"ok": True}
    if operation not in ("translate", "speech"):
        raise AppError(422, "Unknown AI operation.")
    source = await readable(db, payload["kind"], payload["id"])
    if not source:
        raise AppError(404, "This entry is no longer available.")
    language = payload["language"]
    translated = source["language"] != language
    text = await providers.translator.translate(source["body"], language) if translated else source["body"]
    if not await readable(db, payload["kind"], payload["id"]):
        raise AppError(404, "This entry is no longer available.")
    result = {"text": text, "language": language, "translated": translated}
    if operation == "speech":
        audio = await providers.speech.speak(text, language)
        result["audio"] = "data:audio/wav;base64," + base64.b64encode(audio).decode()
    if not await readable(db, payload["kind"], payload["id"]):
        raise AppError(404, "This entry is no longer available.")
    return result


async def process(queue, providers, job):
    async def keep_alive():
        while True:
            await asyncio.sleep(max(0.1, queue.s.job_lease_seconds / 3))
            if not await queue.heartbeat(job):
                return

    token = job_context.set(job["id"])
    heartbeat = asyncio.create_task(keep_alive())
    work = asyncio.create_task(execute(queue.db, queue.s, providers, job))
    started = time.monotonic()
    try:
        done, _ = await asyncio.wait({heartbeat, work}, return_when=asyncio.FIRST_COMPLETED)
        if work not in done:
            work.cancel()
            return
        result = await work
        await queue.complete(job, result)
    except AppError as error:
        await queue.fail(job, error)
    except asyncio.CancelledError:
        # The durable claim expires and another worker may retry.
        raise
    except Exception as error:
        logger.error("Worker task failed: %s", type(error).__name__)
        await queue.fail(
            job, AppError(502, "This task could not be completed. Please try again.", retryable=True)
        )
    finally:
        work.cancel()
        heartbeat.cancel()
        await asyncio.gather(work, heartbeat, return_exceptions=True)
        job_context.reset(token)
        logger.info(
            json.dumps(
                {
                    "event": "job.finished",
                    "job_id": job["id"],
                    "operation": job["operation"],
                    "attempt": job["attempts"],
                    "correlation_id": job["correlation_id"],
                    "duration_ms": round((time.monotonic() - started) * 1000),
                }
            )
        )


async def run():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = get_settings()
    db, stop = Database(settings.database_url), asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    queue = PostgresQueue(db, settings)
    logger.info(
        "Kiez-py worker started: interactive=%s chronicle=%s",
        settings.interactive_concurrency,
        settings.chronicle_concurrency,
    )
    active = set()
    last_schedule, last_cleanup = 0.0, 0.0
    try:
        async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
            providers = build_providers(settings, client, db)
            while not stop.is_set():
                try:
                    now = time.monotonic()
                    if now - last_cleanup > 30:
                        await queue.cleanup()
                        last_cleanup = now
                    if (
                        now - last_schedule > settings.scheduler_interval_seconds
                        and capabilities(settings)["features"]["chronicle"]
                    ):
                        await schedule(db, settings)
                        last_schedule = now
                    for lane, capacity in [
                        ("interactive", settings.interactive_concurrency),
                        ("chronicle", settings.chronicle_concurrency),
                    ]:
                        for _ in range(capacity):
                            job = await queue.claim(lane)
                            if not job:
                                break
                            task = asyncio.create_task(process(queue, providers, job))
                            active.add(task)
                            task.add_done_callback(active.discard)
                except Exception as error:
                    logger.error("Worker polling unavailable: %s", type(error).__name__)
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_seconds)
            for task in active:
                task.cancel()
            await asyncio.gather(*active, return_exceptions=True)
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(run())
