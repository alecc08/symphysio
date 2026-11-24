"""FastAPI dependencies: shared DB handle and cookie-session authentication."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, Response, status

from .db import Database
from .i18n import from_headers, negotiate, t
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
        # Nobody is signed in, so the only language signal is the one the client
        # sent. That is still worth honouring: this is the response the sign-in
        # screen shows most, and a French user should not read an English 401.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("err.not_authenticated", negotiate(request.headers.get("accept-language"))),
            headers={"WWW-Authenticate": "Session"},
        )
    if auth.renewed:
        set_session_cookies(response, settings, auth.token, auth.expires_at_utc)
    return auth.user


AuthedUser = Annotated[dict[str, Any], Depends(current_user)]


async def account_locale(request: Request, user: AuthedUser) -> str:
    """The language this response should be written in.

    A dependency rather than a call in each handler, because the precedence
    matters and every handler used to solve it differently: the account wins
    when there is one, so a French person whose browser menu is set to English
    still reads French errors.
    """
    return from_headers(request.headers, user)


def client_locale(request: Request) -> str:
    """The same answer for a route with no session yet (the sign-up picker)."""
    return negotiate(request.headers.get("accept-language"))


LocaleDep = Annotated[str, Depends(account_locale)]
ClientLocaleDep = Annotated[str, Depends(client_locale)]
