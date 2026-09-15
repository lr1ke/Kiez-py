import asyncio
import time
import uuid

from app.db.seed import seed
from app.security.service import sign


async def post_note(client, **updates):
    location = await client.post(
        "/api/location", json={"latitude": 52.4917, "longitude": 13.415, "accuracy": 10}
    )
    assert location.status_code == 200, location.text
    value = dict(
        nickname="Visitor",
        body="A bicycle bell and quiet rain.",
        language="en",
        inputMode="text",
        locationToken=location.json()["token"],
        idempotencyKey=str(uuid.uuid4()),
        website="",
    )
    value.update(updates)
    return await client.post("/api/contributions", json=value), value


async def test_keyless_reading_berlin_and_no_hamburg(client):
    assert (await client.get("/healthz")).json() == {"ok": True}
    items = (await client.get("/api/neighborhoods")).json()
    assert [i["neighborhood"]["id"] for i in items] == [
        "graefekiez",
        "reuterkiez",
        "bergmannkiez",
        "schillerkiez",
    ]
    assert all(i["latest"] is None for i in items)
    assert (await client.get("/api/neighborhoods/hafencity")).status_code == 404
    assert (
        await client.post("/api/location", json={"latitude": 53.54057, "longitude": 9.99437, "accuracy": 10})
    ).status_code == 422
    assert (await client.get("/api/neighborhoods/graefekiez/archive/2026-02-30")).status_code == 404
    assert (await client.get("/api/neighborhoods/graefekiez/archive/2026-01-01")).json() is None
    assert not (await client.get("/api/capabilities")).json()["available"]


async def test_publish_retry_latest_and_session(client, db):
    first, value = await post_note(client)
    assert first.status_code == 201, first.text
    value["locationToken"] = "expired-token-but-saved-retry"
    retries = await asyncio.gather(*(client.post("/api/contributions", json=value) for _ in range(3)))
    assert all(r.json()["id"] == first.json()["id"] for r in retries)
    second, _ = await post_note(client, body="Another moment.")
    assert second.status_code == 201
    assert (await client.get("/api/latest?kiez=graefekiez")).json()["id"] == second.json()["id"]
    assert (await db.one("SELECT count(*) AS count FROM contributions"))["count"] == 2
    assert (await client.get("/api/session")).json()["nickname"] == "Visitor"
    old = await client.post(
        "/api/translate", json={"kind": "contribution", "id": first.json()["id"], "language": "de"}
    )
    assert old.status_code == 404


async def test_concurrent_new_idempotency_key(client, db):
    loc = (
        await client.post("/api/location", json={"latitude": 52.4917, "longitude": 13.415, "accuracy": 10})
    ).json()
    value = dict(
        nickname="Concurrent",
        body="One saved moment.",
        language="en",
        inputMode="text",
        locationToken=loc["token"],
        idempotencyKey=str(uuid.uuid4()),
    )
    responses = await asyncio.gather(*(client.post("/api/contributions", json=value) for _ in range(3)))
    assert all(r.status_code in (200, 201) for r in responses), [r.text for r in responses]
    assert len({r.json()["id"] for r in responses}) == 1
    assert (await db.one("SELECT count(*) AS count FROM contributions"))["count"] == 1


async def test_presence_session_and_boundary_version(client, db, settings):
    _, value = await post_note(client)
    value["idempotencyKey"] = str(uuid.uuid4())
    value["locationToken"] = sign(
        settings, {"sid": "someone-else", "kiez": "graefekiez", "exp": time.time() * 1000 + 50000}
    )
    assert (await client.post("/api/contributions", json=value)).status_code == 403
    _, value = await post_note(client)
    value["idempotencyKey"] = str(uuid.uuid4())
    await db.execute("UPDATE neighborhoods SET boundary_version='revised' WHERE id='graefekiez'")
    assert (await client.post("/api/contributions", json=value)).status_code == 403


async def test_validation_limits_origin_and_permissions(client):
    assert (
        await client.post("/api/location", json={"latitude": True, "longitude": 13, "accuracy": 10})
    ).status_code == 400
    assert (await client.post("/api/location", content="x" * 32001)).status_code == 413
    assert (
        await client.post("/api/location", headers={"origin": "https://elsewhere.test"}, json={})
    ).status_code == 403
    assert (await client.post("/api/admin/remove", json={"id": "fake"})).status_code == 401
    assert (await client.get("/api/cron")).status_code == 401
    response, _ = await post_note(client, body=" ")
    assert response.status_code == 400
    response, _ = await post_note(client, website="https://spam.test")
    assert response.status_code == 400
    response, _ = await post_note(client, body="https://a https://b https://c https://d")
    assert response.status_code == 422


async def test_reports_removal_and_archive_redaction(client, db):
    await seed(db, "2026-01-12")
    response, _ = await post_note(client)
    entry = response.json()["id"]
    assert (await client.post("/api/report", json={"id": entry})).status_code == 200
    await client.post("/api/report", json={"id": entry})
    assert (await db.one("SELECT count(*) AS count FROM reports"))["count"] == 1
    await db.execute(
        "UPDATE chronicles SET source_ids=jsonb_build_array(CAST(:id AS text)) WHERE neighborhood_id='graefekiez'",
        id=entry,
    )
    removed = await client.post(
        "/api/admin/remove", json={"id": entry}, headers={"authorization": "Bearer admin-test"}
    )
    assert removed.status_code == 200
    assert (await client.get("/api/latest?kiez=graefekiez")).json() is None
    stories = (await client.get("/api/neighborhoods/graefekiez/archive")).json()
    assert all(
        c["status"] == "review" and c["body"] == "" and c["title"] == "" and c["source_ids"] == []
        for c in stories
    )


async def test_demo_reset_preserves_real_notes(client, db):
    real, _ = await post_note(client)
    await seed(db, "2026-01-12")
    await seed(db, "2026-01-12")
    assert (await db.one("SELECT count(*) AS count FROM contributions"))["count"] == 161
    await seed(db, "2026-01-13", reset_demo=True)
    assert (await db.one("SELECT count(*) AS count FROM contributions"))["count"] == 161
    assert await db.one("SELECT id FROM contributions WHERE id=:id", id=real.json()["id"])


async def test_featured_chronicles_are_bounded_and_public(client, db):
    await seed(db, "2026-01-12")
    cards = (await client.get("/api/featured-chronicles")).json()
    assert len(cards) == 3
    assert [c["neighborhood"]["id"] for c in cards] == ["graefekiez", "reuterkiez", "bergmannkiez"]
    assert all(c["story"]["diary_date"] == "2026-01-11" for c in cards)
    assert all("last_error" not in c["story"] and "claim_token" not in c["story"] for c in cards)
