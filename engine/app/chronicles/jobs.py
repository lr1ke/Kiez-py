import json
import uuid

from app.ai.workflows.chronicle import create_chronicle
from app.dates import diary_date
from app.errors import AppError
from app.security.service import rate_limit


async def schedule(db, settings):
    async with db.transaction() as tx:
        await tx.execute("SELECT pg_advisory_xact_lock(731926)")
        await tx.execute(
            """INSERT INTO chronicles(id,neighborhood_id,diary_date)
            SELECT neighborhood_id||':'||diary_date,neighborhood_id,diary_date FROM contributions
            WHERE diary_date<:today AND visibility='visible' GROUP BY neighborhood_id,diary_date
            ON CONFLICT DO NOTHING""",
            today=diary_date(),
        )
        candidates = await tx.rows(
            """SELECT c.id FROM chronicles c LEFT JOIN ai_jobs j ON j.dedupe_key='chronicle:'||c.id
            WHERE c.diary_date<:today AND c.status IN ('pending','failed')
            AND (j.id IS NULL OR (j.status='failed' AND j.finished_at<now()-interval '5 minutes'))
            ORDER BY c.diary_date LIMIT 100""",
            today=diary_date(),
        )
        for row in candidates:
            await rate_limit(tx, f"ai-budget:{diary_date()}", settings.ai_daily_task_limit, 86400)
            await tx.execute(
                """INSERT INTO ai_jobs(id,operation,lane,payload,dedupe_key,max_attempts,expires_at)
                VALUES (:id,'chronicle','chronicle',CAST(:payload AS jsonb),:key,:attempts,now()+interval '1 day')
                ON CONFLICT(dedupe_key) DO UPDATE SET status='pending',attempts=0,available_at=now(),
                    expires_at=now()+interval '1 day',error=NULL,error_status=NULL,finished_at=NULL,result=NULL""",
                id=str(uuid.uuid4()),
                payload=json.dumps({"id": row["id"]}),
                key=f"chronicle:{row['id']}",
                attempts=settings.job_max_attempts,
            )
        return {"enqueued": len(candidates)}


async def generate(db, settings, providers, job):
    chronicle_id = job["payload"]["id"]
    async with db.transaction() as tx:
        current = await tx.one(
            """SELECT id FROM ai_jobs WHERE id=:id AND claim_token=:token
            AND status='running' AND lease_until>now() AND expires_at>now() FOR UPDATE""",
            id=job["id"],
            token=job["claim_token"],
        )
        if not current:
            raise AppError(409, "Worker claim expired.")
        c = await tx.one(
            """UPDATE chronicles SET status='generating',claim_token=:token,claimed_at=now()
            WHERE id=:id AND diary_date<:today AND status IN ('pending','failed','generating') RETURNING *""",
            id=chronicle_id,
            today=diary_date(),
            token=job["claim_token"],
        )
    if not c:
        return {"skipped": True}
    entries = await db.rows(
        """SELECT id,body,language FROM contributions WHERE neighborhood_id=:id
        AND diary_date=:day AND visibility='visible' ORDER BY created_at,id""",
        id=c["neighborhood_id"],
        day=c["diary_date"],
    )
    if not entries:
        await db.execute(
            "DELETE FROM chronicles WHERE id=:id AND claim_token=:token",
            id=chronicle_id,
            token=job["claim_token"],
        )
        return {"quiet": True}
    draft = await create_chronicle(entries, providers.narrative)
    ids = [e["id"] for e in entries]
    async with db.transaction() as tx:
        # Lock sources before the Chronicle, matching moderation's lock order.
        visible = await tx.rows(
            """SELECT id,visibility FROM contributions
            WHERE id IN (SELECT jsonb_array_elements_text(CAST(:ids AS jsonb))) ORDER BY id FOR SHARE""",
            ids=json.dumps(ids),
        )
        if len(visible) != len(ids) or any(e["visibility"] != "visible" for e in visible):
            raise AppError(409, "Source changed; generation must be retried.", retryable=True)
        current = await tx.one(
            """SELECT id FROM ai_jobs WHERE id=:id AND status='running' AND claim_token=:token
            AND lease_until>now() AND expires_at>now() FOR UPDATE""",
            id=job["id"],
            token=job["claim_token"],
        )
        if not current:
            raise AppError(409, "Worker claim expired.")
        row = await tx.one(
            """UPDATE chronicles SET title=:title,body=:body,coverage=CAST(:coverage AS jsonb),
            source_ids=CAST(:ids AS jsonb),contribution_count=:count,model=:model,provider=:provider,prompt_version='chronicle-v1',
            generated_at=now(),published_at=now(),last_error=NULL,status='published'
            WHERE id=:id AND claim_token=:token AND status='generating' RETURNING id""",
            id=chronicle_id,
            token=job["claim_token"],
            title=draft.title,
            body=draft.body,
            coverage=json.dumps(draft.coverage),
            ids=json.dumps(ids),
            count=len(ids),
            model=providers.narrative.model_id,
            provider=providers.narrative.provider_name,
        )
        if not row:
            raise AppError(409, "Chronicle changed during generation.")
    return {"published": chronicle_id}
