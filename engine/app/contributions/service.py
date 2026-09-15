import uuid

from app.dates import diary_date
from app.errors import AppError
from app.neighborhoods.service import catalog
from app.security.service import rate_limit, verify

PUBLIC_FIELDS = "id,neighborhood_id,nickname,body,language,input_mode,created_at,diary_date,demo_dataset"


async def latest(db, slug, day=None):
    return await db.one(
        f"""SELECT {PUBLIC_FIELDS} FROM contributions WHERE neighborhood_id=:id
        AND diary_date=:day AND visibility='visible' ORDER BY created_at DESC,id DESC LIMIT 1""",
        id=slug,
        day=day or diary_date(),
    )


async def summaries(db):
    # Fixed number of queries; adding neighborhoods does not add round trips.
    neighborhoods = await catalog(db)
    current = await db.rows(
        f"""SELECT DISTINCT ON (neighborhood_id) {PUBLIC_FIELDS}
        FROM contributions WHERE diary_date=:day AND visibility='visible'
        ORDER BY neighborhood_id,created_at DESC,id DESC""",
        day=diary_date(),
    )
    counts = await db.rows(
        """SELECT neighborhood_id,count(*) AS count FROM contributions
        WHERE diary_date=:day AND visibility='visible' GROUP BY neighborhood_id""",
        day=diary_date(),
    )
    archived = await db.rows(
        "SELECT neighborhood_id,count(*) AS count FROM chronicles WHERE status='published' GROUP BY neighborhood_id"
    )
    entries = {r["neighborhood_id"]: r for r in current}
    counts = {r["neighborhood_id"]: r["count"] for r in counts}
    archives = {r["neighborhood_id"]: r["count"] for r in archived}
    return [
        dict(
            neighborhood=n,
            latest=entries.get(n["id"]),
            count=counts.get(n["id"], 0),
            archiveCount=archives.get(n["id"], 0),
        )
        for n in neighborhoods
    ]


async def readable(db, kind, entry_id):
    if kind == "contribution":
        row = await db.one("SELECT * FROM contributions WHERE id=:id AND visibility='visible'", id=entry_id)
        if row and (await latest(db, row["neighborhood_id"]) or {}).get("id") == entry_id:
            return {"body": row["body"], "language": row["language"]}
    else:
        return await db.one(
            "SELECT body,language FROM chronicles WHERE id=:id AND status='published'", id=entry_id
        )
    return None


async def publish(db, settings, sid, value):
    key = f"{sid}:{value.idempotencyKey}"
    existing = await db.one(
        "SELECT id,neighborhood_id FROM contributions WHERE idempotency_key=:key", key=key
    )
    if existing:
        return existing, False
    token = verify(settings, value.locationToken)
    if not token or token.get("sid") != sid or not isinstance(token.get("kiez"), str):
        raise AppError(403, "Please check your location again before publishing. Your draft is safe.")
    await rate_limit(db, f"publish:{sid}", 4)
    import re

    if len(re.findall(r"https?://", value.body)) > 3:
        raise AppError(422, "Please share a moment with fewer links.")
    async with db.transaction() as tx:
        # Serialize boundary changes against publication.
        n = await tx.one(
            "SELECT boundary_version FROM neighborhoods WHERE id=:id AND active FOR SHARE", id=token["kiez"]
        )
        if not n or n["boundary_version"] != token.get("boundary_version"):
            raise AppError(403, "Please check your location again before publishing. Your draft is safe.")
        row = await tx.one(
            """INSERT INTO contributions
            (id,neighborhood_id,nickname,body,language,input_mode,diary_date,session_id,idempotency_key)
            VALUES (:id,:kiez,:nickname,:body,:language,:mode,:day,:sid,:key)
            ON CONFLICT(idempotency_key) DO UPDATE SET idempotency_key=EXCLUDED.idempotency_key
            RETURNING id,neighborhood_id""",
            id=str(uuid.uuid4()),
            kiez=token["kiez"],
            nickname=value.nickname,
            body=value.body,
            language=value.language,
            mode=value.inputMode,
            day=diary_date(),
            sid=sid,
            key=key,
        )
        await tx.execute(
            "UPDATE sessions SET nickname=:nickname WHERE id=:sid", nickname=value.nickname, sid=sid
        )
    return row, True
