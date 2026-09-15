import base64
import hashlib
import hmac
import json
import time
import uuid

from app.errors import AppError


def b64(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def sign(settings, data):
    payload = b64(json.dumps(data, separators=(",", ":")).encode())
    signature = b64(hmac.new(settings.session_secret.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def verify(settings, token):
    try:
        payload, signature = token.split(".")
        expected = b64(hmac.new(settings.session_secret.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if (
            not isinstance(data, dict)
            or not isinstance(data.get("exp"), (int, float))
            or data["exp"] < time.time() * 1000
        ):
            return None
        return data
    except (ValueError, TypeError, UnicodeError):
        return None


async def session(request, response, db, settings):
    data = verify(settings, request.cookies.get("kiez-session", ""))
    sid = data.get("sid") if data else None
    if not isinstance(sid, str):
        sid = str(uuid.uuid4())
        response.set_cookie(
            "kiez-session",
            sign(settings, {"sid": sid, "exp": (time.time() + 30 * 86400) * 1000}),
            max_age=30 * 86400,
            httponly=True,
            samesite="lax",
            secure=settings.environment == "production",
            path="/",
        )
    await db.execute("INSERT INTO sessions(id) VALUES (:id) ON CONFLICT DO NOTHING", id=sid)
    return sid


async def rate_limit(db, key, limit, seconds=60):
    row = await db.one(
        """INSERT INTO rate_limits(key,hits,expires_at)
        VALUES (:key,1,now()+make_interval(secs => :seconds))
        ON CONFLICT(key) DO UPDATE SET
        hits=CASE WHEN rate_limits.expires_at<now() THEN 1 ELSE rate_limits.hits+1 END,
        expires_at=CASE WHEN rate_limits.expires_at<now() THEN now()+make_interval(secs => :seconds)
                       ELSE rate_limits.expires_at END RETURNING hits""",
        key=key,
        seconds=seconds,
    )
    if row["hits"] > limit:
        raise AppError(429, "A little pause, please. Try again in a minute.")


def authorize(request, secret):
    supplied = request.headers.get("authorization", "")
    if not secret or not hmac.compare_digest(supplied, f"Bearer {secret}"):
        raise AppError(401, "Authorization required.")
