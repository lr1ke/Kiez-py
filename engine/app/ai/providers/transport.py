import contextvars
import json
import logging
import time

import httpx

from app.errors import AppError

job_context = contextvars.ContextVar("job_context", default=None)
logger = logging.getLogger("kiez.ai")


class Transport:
    def __init__(self, client: httpx.AsyncClient, db=None):
        self.client, self.db = client, db

    async def post(self, url, *, provider, model, operation, **kwargs):
        started, outcome, usage = time.monotonic(), "failed", None
        try:
            response = await self.client.post(url, **kwargs)
            if not response.is_success:
                status = response.status_code
                retry = response.headers.get("retry-after", "")
                retry_after = min(int(retry), 3600) if retry.isdigit() else 0
                raise AppError(
                    429 if status == 429 else 502,
                    f"{provider} has reached its rate or quota limit. Please try again later. Text is still available."
                    if status == 429
                    else f"{provider} could not complete this request. Please try again.",
                    retryable=status == 429 or status >= 500,
                    retry_after=retry_after,
                )
            if "json" in response.headers.get("content-type", ""):
                data = response.json()
                usage = data.get("usage") or data.get("usageMetadata")
            outcome = "completed"
            return response
        except httpx.HTTPError:
            raise AppError(
                502, f"{provider} is temporarily unavailable. Please try again.", retryable=True
            ) from None
        finally:
            elapsed = round((time.monotonic() - started) * 1000)
            job = job_context.get()
            logger.info(
                json.dumps(
                    dict(
                        event="ai.call",
                        job_id=job,
                        operation=operation,
                        provider=provider,
                        model=model,
                        duration_ms=elapsed,
                        outcome=outcome,
                        usage=usage,
                    )
                )
            )
            if self.db and job:
                try:
                    await self.db.execute(
                        """INSERT INTO ai_usage(job_id,operation,provider,model,duration_ms,outcome,usage)
                        VALUES (:job,:operation,:provider,:model,:duration,:outcome,CAST(:usage AS jsonb))""",
                        job=job,
                        operation=operation,
                        provider=provider,
                        model=model,
                        duration=elapsed,
                        outcome=outcome,
                        usage=json.dumps(usage),
                    )
                except Exception:
                    logger.warning("AI usage persistence unavailable", extra={"job_id": job})
