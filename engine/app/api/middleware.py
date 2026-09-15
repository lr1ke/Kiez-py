"""Bound requests before multipart parsing, enforce origin and attach request IDs."""

import json
import logging
import time
import uuid

from starlette.responses import JSONResponse

logger = logging.getLogger("kiez.http")


class RequestGuard:
    def __init__(self, app, public_origin):
        self.app, self.origin = app, public_origin.rstrip("/")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        start = time.monotonic()
        correlation = str(uuid.uuid4())
        scope.setdefault("state", {})["correlation_id"] = correlation
        headers = dict(scope.get("headers", []))

        async def send_headers(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).extend(
                    [(b"cache-control", b"no-store"), (b"x-request-id", correlation.encode())]
                )
                logger.info(
                    json.dumps(
                        {
                            "event": "http.request",
                            "method": scope["method"],
                            "path": scope["path"],
                            "status": message["status"],
                            "correlation_id": correlation,
                            "duration_ms": round((time.monotonic() - start) * 1000),
                        }
                    )
                )
            await send(message)

        if scope["method"] in ("POST", "PUT", "PATCH", "DELETE"):
            origin = headers.get(b"origin", b"").decode(errors="replace")
            if origin and origin != self.origin and scope["path"] != "/api/cron":
                return await JSONResponse({"error": "This request must come from Kiez Diary."}, 403)(
                    scope, receive, send_headers
                )
            limit = 4500000 if scope["path"] == "/api/transcribe" else 32000
            chunks, size = [], 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                size += len(chunk)
                if size > limit:
                    return await JSONResponse({"error": "Request too large."}, 413)(
                        scope, receive, send_headers
                    )
                chunks.append(chunk)
                if not message.get("more_body", False):
                    break
            body = b"".join(chunks)
            delivered = False
            original_receive = receive

            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await original_receive()

            receive = replay
        await self.app(scope, receive, send_headers)
