import uuid

from app.contributions.service import readable
from app.errors import AppError


async def report(db, sid, entry_id):
    if not await readable(db, "contribution", entry_id):
        raise AppError(404, "That moment is no longer visible.")
    await db.execute(
        """INSERT INTO reports(id,contribution_id,session_id)
        VALUES (:id,:entry,:sid) ON CONFLICT DO NOTHING""",
        id=str(uuid.uuid4()),
        entry=entry_id,
        sid=sid,
    )


async def remove(db, entry_id):
    async with db.transaction() as tx:
        # The worker locks source rows before publication; removal uses the same ordering.
        await tx.execute("UPDATE contributions SET visibility='removed' WHERE id=:id", id=entry_id)
        await tx.execute(
            "UPDATE chronicles SET status='review' WHERE source_ids @> CAST(:ids AS jsonb)",
            ids=__import__("json").dumps([entry_id]),
        )
        await tx.execute(
            """UPDATE ai_jobs SET result=NULL,status='cancelled',payload='{}'::jsonb,
            error='This entry is no longer available.',error_status=404,finished_at=now()
            WHERE operation IN ('translate','speech') AND
            (payload->>'id'=:id OR (payload->>'kind'='chronicle' AND payload->>'id' IN
             (SELECT id FROM chronicles WHERE status='review')))""",
            id=entry_id,
        )


async def reports(db):
    return await db.rows("""SELECT r.id,r.contribution_id,r.created_at,c.body,c.nickname,c.visibility
        FROM reports r JOIN contributions c ON c.id=r.contribution_id ORDER BY r.created_at DESC LIMIT 100""")
