import logging
import math
import time
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile

from app.ai.registry import capabilities
from app.api.dependencies import database, queue, session_id, settings
from app.api.models import (
    AcceptedJob,
    Chronicle,
    ContentInput,
    Contribution,
    ContributionInput,
    FeaturedChronicle,
    IdInput,
    JobStatus,
    LocationInput,
    LocationResult,
    Neighborhood,
    Publication,
    SessionInfo,
    Summary,
)
from app.chronicles.jobs import schedule
from app.chronicles.service import archive, featured
from app.contributions.service import latest, publish, readable, summaries
from app.errors import AppError
from app.moderation import service as moderation
from app.neighborhoods.service import get_neighborhood
from app.security.service import authorize, rate_limit, sign

router = APIRouter(prefix="/api")
Session = Annotated[str, Depends(session_id)]
logger = logging.getLogger("kiez.api")


async def mutation(request, sid):
    await rate_limit(database(request), f"requests:{sid}", 60)


@router.get("/neighborhoods", response_model=list[Summary])
async def neighborhoods(request: Request):
    return await summaries(database(request))


@router.get("/neighborhoods/{slug}", response_model=Neighborhood)
async def neighborhood(slug: str, request: Request):
    return await get_neighborhood(database(request), slug)


@router.get("/neighborhoods/{slug}/archive", response_model=list[Chronicle])
async def archive_list(slug: str, request: Request):
    await get_neighborhood(database(request), slug)
    return await archive(database(request), slug)


@router.get("/neighborhoods/{slug}/archive/{day}", response_model=Chronicle | None)
async def archive_day(slug: str, day: str, request: Request):
    await get_neighborhood(database(request), slug)
    try:
        if len(day) != 10 or date.fromisoformat(day).isoformat() != day:
            raise ValueError()
    except ValueError:
        raise AppError(404, "Date not found.") from None
    return next((c for c in await archive(database(request), slug) if c["diary_date"] == day), None)


@router.get("/latest", response_model=Contribution | None)
async def latest_entry(request: Request, kiez: str = ""):
    return await latest(database(request), kiez)


@router.get("/capabilities")
async def feature_capabilities(request: Request):
    return capabilities(settings(request))


@router.get("/session", response_model=SessionInfo)
async def current_session(request: Request, sid: Session):
    return await database(request).one("SELECT nickname FROM sessions WHERE id=:id", id=sid)


@router.post("/location", response_model=LocationResult)
async def location(value: LocationInput, request: Request, sid: Session):
    await mutation(request, sid)
    n = await request.app.state.resolver.resolve(
        database(request), value.latitude, value.longitude, value.accuracy
    )
    token = sign(
        settings(request),
        {
            "sid": sid,
            "kiez": n["id"],
            "boundary_version": n["boundary_version"],
            "exp": (time.time() + 300) * 1000,
        },
    )
    return {"neighborhood": n, "token": token}


@router.post("/contributions", response_model=Publication)
async def contributions(value: ContributionInput, request: Request, response: Response, sid: Session):
    await mutation(request, sid)
    row, created = await publish(database(request), settings(request), sid, value)
    response.status_code = 201 if created else 200
    if value.language == "und" and capabilities(settings(request))["features"]["detect"]:
        try:
            await queue(request).enqueue(
                "detect",
                {"id": row["id"]},
                sid,
                dedupe=f"detect:{row['id']}",
                correlation_id=request.state.correlation_id,
            )
        except Exception as error:
            # A detector outage or exhausted AI budget cannot turn a saved note into a failed submission.
            logger.warning("Language detection enqueue failed: %s", type(error).__name__)
    return row


@router.post("/report")
async def report(value: IdInput, request: Request, sid: Session):
    await mutation(request, sid)
    await rate_limit(database(request), f"reports:{sid}", 5)
    await moderation.report(database(request), sid, value.id)
    return {"ok": True}


@router.get("/admin/reports")
async def reports(request: Request):
    authorize(request, settings(request).admin_secret)
    return await moderation.reports(database(request))


@router.post("/admin/remove")
async def remove(value: IdInput, request: Request):
    authorize(request, settings(request).admin_secret)
    await moderation.remove(database(request), value.id)
    return {"ok": True}


@router.get("/admin/metrics")
async def metrics(request: Request):
    authorize(request, settings(request).admin_secret)
    usage = await database(request).rows("""SELECT operation,provider,model,count(*) AS calls,
        avg(duration_ms) AS average_duration_ms,count(*) FILTER(WHERE outcome='failed') AS failures
        FROM ai_usage WHERE created_at>now()-interval '1 day' GROUP BY operation,provider,model""")
    return {"jobs": await queue(request).metrics(), "ai": usage}


@router.get("/cron", operation_id="cron_get")
@router.post("/cron", operation_id="cron_post")
async def cron(request: Request):
    authorize(request, settings(request).cron_secret)
    await queue(request).cleanup()
    return await schedule(database(request), settings(request))


def task_key(request, sid, operation):
    key = request.headers.get("idempotency-key")
    if not key:
        return None
    try:
        return f"{operation}:{sid}:{UUID(key)}"
    except ValueError:
        raise AppError(400, "Please use a UUID idempotency key.") from None


def require_feature(request, feature):
    if not capabilities(settings(request))["features"][feature]:
        raise AppError(503, "This AI feature is not connected yet. You can still read and write.")


@router.post("/transcribe", status_code=202, response_model=AcceptedJob)
async def transcribe(
    request: Request, sid: Session, audio: UploadFile = File(...), duration: str = Form(...)
):
    await mutation(request, sid)
    await rate_limit(database(request), f"audio:{sid}", 6)
    await rate_limit(database(request), "global:audio", 60)
    require_feature(request, "transcribe")
    try:
        length = float(duration)
    except ValueError:
        length = float("nan")
    mime = (audio.content_type or "").split(";")[0]
    data = await audio.read(4000001)
    await audio.close()
    if not data or len(data) > 4000000 or not math.isfinite(length) or not 0 < length <= 61:
        raise AppError(422, "Use a recording up to one minute and 4 MB.")
    if mime not in ("audio/webm", "audio/mp4", "audio/ogg", "audio/wav"):
        raise AppError(
            422, "This recording format is not supported. Try another browser or type your moment."
        )
    job = await queue(request).enqueue(
        "transcribe",
        {"mime_type": mime},
        sid,
        audio=data,
        dedupe=task_key(request, sid, "transcribe"),
        correlation_id=request.state.correlation_id,
    )
    return {"jobId": job, "status": "pending"}


async def language_task(operation, value, request, sid):
    await mutation(request, sid)
    await rate_limit(database(request), f"language:{sid}", 12)
    await rate_limit(database(request), "global:language", 120)
    if value.language not in settings(request).languages:
        raise AppError(422, "This language is not enabled yet.")
    source = await readable(database(request), value.kind, value.id)
    if not source:
        raise AppError(404, "This entry is no longer available.")
    if source["language"] != value.language:
        require_feature(request, "translate")
    if operation == "speech":
        require_feature(request, "speech")
    job = await queue(request).enqueue(
        operation,
        value.model_dump(),
        sid,
        dedupe=task_key(request, sid, operation),
        correlation_id=request.state.correlation_id,
    )
    return {"jobId": job, "status": "pending"}


@router.post("/translate", status_code=202, response_model=AcceptedJob)
async def translate(value: ContentInput, request: Request, sid: Session):
    return await language_task("translate", value, request, sid)


@router.post("/speech", status_code=202, response_model=AcceptedJob)
async def speech(value: ContentInput, request: Request, sid: Session):
    return await language_task("speech", value, request, sid)


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def job_status(job_id: str, request: Request, sid: Session):
    await rate_limit(database(request), f"poll:{sid}", 180)
    return await queue(request).poll(job_id, sid)


@router.post("/jobs/{job_id}/cancel")
async def cancel(job_id: str, request: Request, sid: Session):
    await mutation(request, sid)
    await queue(request).cancel(job_id, sid)
    return {"ok": True}


@router.get("/featured-chronicles", response_model=list[FeaturedChronicle])
async def featured_chronicles(request: Request):
    return await featured(database(request))
