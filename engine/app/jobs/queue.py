"""PostgreSQL queue: shared capacity, leased claims and fenced completion."""

import json
import uuid
from datetime import UTC, datetime
from typing import Protocol

from app.contributions.service import readable
from app.dates import diary_date
from app.errors import AppError
from app.security.service import rate_limit


class JobQueue(Protocol):
    async def enqueue(self, operation, payload, sid=None, **kwargs) -> str: ...
    async def claim(self, lane) -> dict | None: ...
    async def complete(self, job, result): ...


class PostgresQueue:
    def __init__(self, db, settings):
        self.db, self.s = db, settings

    async def enqueue(self, operation, payload, sid=None, *, dedupe=None, audio=None, correlation_id=None):
        job_id = str(uuid.uuid4())
        async with self.db.transaction() as tx:
            if dedupe:
                existing = await tx.one("SELECT id FROM ai_jobs WHERE dedupe_key=:key", key=dedupe)
                if existing:
                    return existing["id"]
            await rate_limit(tx, f"ai-budget:{diary_date()}", self.s.ai_daily_task_limit, 86400)
            row = await tx.one(
                """INSERT INTO ai_jobs
                (id,operation,lane,session_id,payload,dedupe_key,max_attempts,expires_at,correlation_id)
                VALUES (:id,:operation,:lane,:sid,CAST(:payload AS jsonb),:key,:attempts,
                        now()+make_interval(secs => :ttl),:correlation)
                ON CONFLICT(dedupe_key) DO UPDATE SET dedupe_key=EXCLUDED.dedupe_key RETURNING id""",
                id=job_id,
                operation=operation,
                lane="chronicle" if operation == "chronicle" else "interactive",
                sid=sid,
                payload=json.dumps(payload),
                key=dedupe or job_id,
                attempts=self.s.job_max_attempts,
                ttl=86400 if operation == "chronicle" else self.s.job_ttl_seconds,
                correlation=correlation_id,
            )
            if audio is not None:
                await tx.execute(
                    """INSERT INTO audio_staging(job_id,data,expires_at)
                    VALUES (:id,:data,now()+make_interval(secs => :ttl)) ON CONFLICT DO NOTHING""",
                    id=row["id"],
                    data=audio,
                    ttl=self.s.job_ttl_seconds,
                )
            return row["id"]

    async def claim(self, lane):
        capacity = self.s.chronicle_concurrency if lane == "chronicle" else self.s.interactive_concurrency
        async with self.db.transaction() as tx:
            # Serialize capacity decisions across all worker processes for this lane.
            await tx.execute(
                "SELECT pg_advisory_xact_lock(:key)", key=731924 if lane == "chronicle" else 731925
            )
            count = await tx.one(
                """SELECT count(*) AS count FROM ai_jobs
                WHERE lane=:lane AND status='running' AND lease_until>now() AND expires_at>now()""",
                lane=lane,
            )
            if count["count"] >= capacity:
                return None
            token = str(uuid.uuid4())
            return await tx.one(
                """UPDATE ai_jobs SET status='running',claim_token=:token,
                lease_until=now()+make_interval(secs => :lease),attempts=attempts+1
                WHERE id=(SELECT id FROM ai_jobs WHERE lane=:lane AND expires_at>now()
                    AND attempts<max_attempts AND ((status='pending' AND available_at<=now())
                        OR (status='running' AND lease_until<now()))
                    ORDER BY available_at,created_at FOR UPDATE SKIP LOCKED LIMIT 1)
                RETURNING *""",
                token=token,
                lease=self.s.job_lease_seconds,
                lane=lane,
            )

    async def heartbeat(self, job):
        return await self.db.one(
            """UPDATE ai_jobs SET lease_until=now()+make_interval(secs => :lease)
            WHERE id=:id AND claim_token=:token AND status='running' AND expires_at>now()
            AND lease_until>now() RETURNING id""",
            id=job["id"],
            token=job["claim_token"],
            lease=self.s.job_lease_seconds,
        )

    async def complete(self, job, result):
        async with self.db.transaction() as tx:
            row = await tx.one(
                """UPDATE ai_jobs SET status='completed',result=CAST(:result AS jsonb),
                finished_at=now(),lease_until=NULL WHERE id=:id AND claim_token=:token AND status='running'
                AND lease_until>now() AND expires_at>now() RETURNING id""",
                id=job["id"],
                token=job["claim_token"],
                result=json.dumps(result),
            )
            if row:
                await tx.execute("DELETE FROM audio_staging WHERE job_id=:id", id=job["id"])
            return row

    async def fail(self, job, error):
        retry = error.retryable and job["attempts"] < job["max_attempts"]
        delay = max(error.retry_after, min(300, 2 ** job["attempts"]))
        async with self.db.transaction() as tx:
            row = await tx.one(
                """UPDATE ai_jobs SET status=:status,error=:error,error_status=:code,
                available_at=now()+make_interval(secs => :delay),lease_until=NULL,
                finished_at=CASE WHEN :retry THEN NULL ELSE now() END
                WHERE id=:id AND claim_token=:token AND status='running' AND lease_until>now() RETURNING id""",
                id=job["id"],
                token=job["claim_token"],
                status="pending" if retry else "failed",
                error=error.message,
                code=error.status,
                delay=delay,
                retry=retry,
            )
            if row and not retry:
                await tx.execute("DELETE FROM audio_staging WHERE job_id=:id", id=job["id"])
            if row and job["operation"] == "chronicle":
                await tx.execute(
                    "UPDATE chronicles SET status='failed',last_error=:error WHERE id=:id AND claim_token=:token AND status='generating'",
                    id=job["payload"]["id"],
                    token=job["claim_token"],
                    error=error.message,
                )

    async def poll(self, job_id, sid):
        job = await self.db.one("SELECT * FROM ai_jobs WHERE id=:id AND session_id=:sid", id=job_id, sid=sid)
        if not job:
            raise AppError(404, "Task not found.")
        if job["expires_at"] <= datetime.now(UTC):
            raise AppError(410, "This task expired. Please try again.")
        if job["operation"] in ("translate", "speech") and job["payload"]:
            if not await readable(self.db, job["payload"]["kind"], job["payload"]["id"]):
                raise AppError(404, "This entry is no longer available.")
        result = {"id": job_id, "status": job["status"]}
        if job["status"] == "completed":
            result["result"] = job["result"]
        elif job["status"] in ("failed", "cancelled"):
            result["error"] = job["error"] or "This task was cancelled."
            result["errorStatus"] = job["error_status"] or 409
        return result

    async def cancel(self, job_id, sid):
        async with self.db.transaction() as tx:
            row = await tx.one(
                """UPDATE ai_jobs SET status='cancelled',result=NULL,payload='{}'::jsonb,
                finished_at=now(),lease_until=NULL WHERE id=:id AND session_id=:sid RETURNING id""",
                id=job_id,
                sid=sid,
            )
            if not row:
                raise AppError(404, "Task not found.")
            await tx.execute("DELETE FROM audio_staging WHERE job_id=:id", id=job_id)

    async def cleanup(self):
        async with self.db.transaction() as tx:
            await tx.execute("""UPDATE ai_jobs SET status='failed',error='Task expired or worker retries exhausted.',
                error_status=504,finished_at=now(),lease_until=NULL WHERE status IN ('pending','running')
                AND (expires_at<now() OR (status='running' AND lease_until<now() AND attempts>=max_attempts))""")
            await tx.execute("""UPDATE chronicles c SET status='failed',last_error='Worker retries exhausted.'
                FROM ai_jobs j WHERE j.operation='chronicle' AND j.payload->>'id'=c.id
                AND j.status='failed' AND c.status='generating' AND c.claim_token=j.claim_token""")
            await tx.execute("""DELETE FROM audio_staging WHERE expires_at<now() OR job_id IN
                (SELECT id FROM ai_jobs WHERE status IN ('failed','cancelled','completed'))""")
            # Results and transient payloads have a bounded lifetime, including completed transcripts/audio.
            await tx.execute(
                "UPDATE ai_jobs SET result=NULL,payload='{}'::jsonb WHERE expires_at<now() AND operation<>'chronicle'"
            )
            await tx.execute("DELETE FROM rate_limits WHERE expires_at<now()")

    async def metrics(self):
        return await self.db.rows("""SELECT lane,status,count(*) AS count,
            extract(epoch FROM now()-min(created_at)) AS oldest_age_seconds
            FROM ai_jobs WHERE expires_at>now() GROUP BY lane,status ORDER BY lane,status""")
