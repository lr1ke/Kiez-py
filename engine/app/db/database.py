from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


class Database:
    def __init__(self, url: str):
        self.engine = create_async_engine(url, pool_size=5, max_overflow=5, pool_pre_ping=True)

    @asynccontextmanager
    async def transaction(self):
        async with self.engine.begin() as connection:
            yield Queries(connection)

    async def rows(self, sql, **params):
        async with self.transaction() as tx:
            return await tx.rows(sql, **params)

    async def one(self, sql, **params):
        rows = await self.rows(sql, **params)
        return rows[0] if rows else None

    async def execute(self, sql, **params):
        async with self.transaction() as tx:
            return await tx.execute(sql, **params)

    async def close(self):
        await self.engine.dispose()


class Queries:
    def __init__(self, connection):
        self.connection = connection

    async def rows(self, sql, **params):
        result = await self.connection.execute(text(sql), params)
        return [dict(row) for row in result.mappings().all()]

    async def one(self, sql, **params):
        rows = await self.rows(sql, **params)
        return rows[0] if rows else None

    async def execute(self, sql, **params):
        return await self.connection.execute(text(sql), params)
