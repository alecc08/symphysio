"""FastAPI dependencies: shared DB handle and cookie-session authentication."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, Response, status

from .db import Database
from .security import authenticate, set_session_cookies
from .settings import Settings


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_db(request: Request) -> Database:
    db: Database = request.app.state.db
    return db


async def current_user(
    request: Request,
    response: Response,
    db: Annotated[Database, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Resolve the session cookie to a user row; rolls the cookie forward."""
    token = request.cookies.get(settings.session_cookie)
    auth = await authenticate(db, settings, token)
    if auth is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Session"},
        )
    if auth.renewed:
        set_session_cookies(response, settings, auth.token, auth.expires_at_utc)
    return auth.user


AuthedUser = Annotated[dict[str, Any], Depends(current_user)]
