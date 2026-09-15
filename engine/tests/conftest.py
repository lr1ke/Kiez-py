import importlib.util
import os
import uuid
from pathlib import Path

import httpx
import pytest
from sqlalchemy.engine import make_url

from app.db.database import Database
from app.db.seed import seed
from app.main import create_app
from app.settings import Settings


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        session_secret="test-secret",
        public_origin="http://test",
        admin_secret="admin-test",
        cron_secret="cron-test",
        demo_data=False,
    )


@pytest.fixture
async def db(settings):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to an isolated PostgreSQL test database to run integration tests.")
    parsed = make_url(url)
    if not parsed.database or not parsed.database.endswith("_test"):
        raise RuntimeError("TEST_DATABASE_URL must name a database ending in _test.")
    admin = Database(url)
    schema = "test_" + uuid.uuid4().hex
    await admin.execute(f"CREATE SCHEMA {schema}")
    scoped_url = parsed.update_query_dict({"options": f"-csearch_path={schema},public"})
    scoped = Database(scoped_url)
    try:
        async with scoped.transaction() as tx:
            for path in sorted((Path(__file__).parents[1] / "migrations/versions").glob("*.py")):
                spec = importlib.util.spec_from_file_location(path.stem, path)
                migration = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(migration)
                for statement in migration.SQL.split(";"):
                    if statement.strip():
                        await tx.execute(statement)
        await seed(scoped, demo=False)
        yield scoped
    finally:
        await scoped.close()
        await admin.execute(f"DROP SCHEMA {schema} CASCADE")
        await admin.close()


@pytest.fixture
async def client(db, settings):
    app = create_app(settings, db)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client
