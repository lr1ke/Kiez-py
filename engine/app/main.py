import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.api.middleware import RequestGuard
from app.api.routes import router
from app.db.database import Database
from app.errors import AppError
from app.jobs.queue import PostgresQueue
from app.neighborhoods.service import GeoJSONResolver
from app.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")


def create_app(settings=None, db=None):
    settings = settings or get_settings()
    owns_db = db is None
    db = db or Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        yield
        if owns_db:
            await db.close()

    app = FastAPI(title="Kiez-py", version="0.1.0", lifespan=lifespan)
    app.state.settings, app.state.db = settings, db
    app.state.queue = PostgresQueue(db, settings)
    app.state.resolver = GeoJSONResolver()
    app.add_middleware(RequestGuard, public_origin=settings.public_origin)
    app.include_router(router)

    @app.exception_handler(AppError)
    async def known_error(request, error):
        return JSONResponse({"error": error.message}, error.status)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, error):
        return JSONResponse({"error": "Please check the submitted fields and try again."}, 400)

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        return JSONResponse(
            {"error": "Not found." if error.status_code == 404 else "Request could not be completed."},
            error.status_code,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request, error):
        logging.getLogger("kiez.api").error("Request failed: %s", type(error).__name__)
        return JSONResponse(
            {"error": "Something went wrong. Your saved contributions are safe. Please try again."}, 500
        )

    @app.get("/healthz")
    async def health():
        return {"ok": True}

    @app.get("/readyz")
    async def ready(request: Request):
        try:
            await request.app.state.db.one("SELECT version_num FROM alembic_version LIMIT 1")
            return {"ok": True}
        except Exception:
            raise AppError(503, "Database is not ready.") from None

    return app


app = create_app()
