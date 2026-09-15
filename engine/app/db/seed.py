"""Versioned catalog and fictional data. Never read the original project's database."""

import argparse
import asyncio
import json
from datetime import UTC, date, datetime, time, timedelta

from app.dates import BERLIN, diary_date
from app.db.database import Database
from app.settings import ROOT, get_settings


def fixtures(anchor):
    date.fromisoformat(anchor)
    groups = json.loads((ROOT / "data/fixtures.json").read_text())
    shift = date.fromisoformat(anchor) - date(2026, 9, 12)
    for group in groups:
        for entry in group["entries"]:
            day = date.fromisoformat(entry["diary_date"]) + shift
            old_time = datetime.fromisoformat(entry["created_at"].replace("Z", "+00:00"))
            if day.isoformat() == anchor:
                timestamp = datetime.combine(day, time(), BERLIN) + timedelta(seconds=old_time.second)
            else:
                timestamp = old_time + shift
            entry["created_at"] = timestamp.astimezone(UTC)
            entry["diary_date"] = day.isoformat()
            entry["id"] = entry["id"].replace("2026-09-12", anchor)
            entry["demo_dataset"] = f"demo-v1-{anchor}"
        c = group["chronicle"]
        if c:
            c["id"] = c["id"].replace("2026-09-12", anchor)
            c["diary_date"] = (date.fromisoformat(c["diary_date"]) + shift).isoformat()
            c["demo_dataset"] = f"demo-v1-{anchor}"
            c["source_ids"] = [x.replace("2026-09-12", anchor) for x in c["source_ids"]]
            c["coverage"] = {k.replace("2026-09-12", anchor): v for k, v in c["coverage"].items()}
    return groups


async def seed(db, anchor=None, demo=True, reset_demo=False):
    async with db.transaction() as tx:
        await tx.execute("SELECT pg_advisory_xact_lock(731923)")
        catalog = json.loads((ROOT / "data/neighborhoods.json").read_text())
        for index, n in enumerate(catalog):
            # Explicit catalog import; startup never overwrites future curated revisions.
            await tx.execute(
                """INSERT INTO neighborhoods
                (id,name,aliases,geometry,boundary_version,district,description,color,center,display_order)
                VALUES (:id,:name,CAST(:aliases AS jsonb),CAST(:geometry AS jsonb),'berlin-prototype-v1',
                        :district,:description,:color,CAST(:center AS jsonb),:order)
                ON CONFLICT(id) DO NOTHING""",
                **{
                    **n,
                    "aliases": json.dumps(n["aliases"]),
                    "geometry": json.dumps(n["geometry"]),
                    "center": json.dumps(n["center"]),
                    "order": index,
                },
            )
        existing = await tx.one("SELECT value FROM settings WHERE key='demo-anchor'")
        anchor = anchor or (existing["value"] if existing else diary_date())
        date.fromisoformat(anchor)
        if reset_demo:
            # Hide any real Chronicle that references a removed demo source.
            await tx.execute("""UPDATE chronicles SET status='review' WHERE demo_dataset IS NULL AND EXISTS
                (SELECT 1 FROM contributions c WHERE c.demo_dataset IS NOT NULL AND source_ids ? c.id)""")
            await tx.execute("DELETE FROM chronicles WHERE demo_dataset IS NOT NULL")
            await tx.execute(
                "DELETE FROM reports WHERE contribution_id IN (SELECT id FROM contributions WHERE demo_dataset IS NOT NULL)"
            )
            await tx.execute("DELETE FROM contributions WHERE demo_dataset IS NOT NULL")
        if not demo:
            return
        if existing and existing["value"] != anchor and not reset_demo:
            raise ValueError("Demo anchor already exists; use --reset-demo to change it.")
        for group in fixtures(anchor):
            for e in group["entries"]:
                await tx.execute(
                    """INSERT INTO contributions
                    (id,neighborhood_id,nickname,body,language,input_mode,created_at,diary_date,idempotency_key,demo_dataset)
                    VALUES (:id,:neighborhood_id,:nickname,:body,:language,:input_mode,:created_at,:diary_date,:id,:demo_dataset)
                    ON CONFLICT DO NOTHING""",
                    **e,
                )
            c = group["chronicle"]
            if c:
                await tx.execute(
                    """INSERT INTO chronicles
                    (id,neighborhood_id,diary_date,title,body,source_ids,contribution_count,status,coverage,
                     model,provider,prompt_version,generated_at,published_at,demo_dataset)
                    VALUES (:id,:neighborhood_id,:diary_date,:title,:body,CAST(:source_ids AS jsonb),8,'published',
                            CAST(:coverage AS jsonb),'editorial-fixture','editorial','fixture-v1',now(),now(),:demo_dataset)
                    ON CONFLICT DO NOTHING""",
                    **{**c, "source_ids": json.dumps(c["source_ids"]), "coverage": json.dumps(c["coverage"])},
                )
        await tx.execute(
            "INSERT INTO settings(key,value) VALUES ('demo-anchor',:anchor) ON CONFLICT(key) DO UPDATE SET value=:anchor",
            anchor=anchor,
        )


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("anchor", nargs="?")
    parser.add_argument("--reset-demo", action="store_true")
    parser.add_argument("--no-demo", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    db = Database(settings.database_url)
    try:
        await seed(
            db,
            args.anchor or settings.demo_anchor_date or None,
            demo=settings.demo_data and not args.no_demo,
            reset_demo=args.reset_demo,
        )
        print("Berlin catalog ready. Demo fixtures seeded if enabled; real contributions preserved.")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
