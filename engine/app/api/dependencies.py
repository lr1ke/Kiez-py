from fastapi import Request, Response

from app.security.service import session


def database(request: Request):
    return request.app.state.db


def settings(request: Request):
    return request.app.state.settings


def queue(request: Request):
    return request.app.state.queue


async def session_id(request: Request, response: Response):
    return await session(request, response, database(request), settings(request))
