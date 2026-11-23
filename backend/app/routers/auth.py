"""Auth endpoints: register, login, logout, session check.

Rate limited per IP (and per account on login) to blunt password spraying.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from ..db import Database
from ..deps import AuthedUser, get_db, get_settings
from ..ids import new_id, now_utc
from ..password_policy import check_password
from ..schemas import AuthOut, LoginRequest, RegisterRequest, UserOut
from ..security import (
    clear_session_cookies,
    create_session,
    hash_password,
    password_needs_rehash,
    revoke_all_sessions,
    revoke_session,
    set_session_cookies,
    token_digest,
    verify_password,
)
from ..seed import seed_catalog
from ..settings import Settings

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    """Best-effort client address (trust X-Forwarded-For only behind your proxy)."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# Verified instead of a real hash when the account does not exist, so "no such
# user" and "wrong password" cost the same amount of Argon2 work.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(24))


def _retry_header(seconds: int) -> dict[str, str]:
    return {"Retry-After": str(seconds), "Cache-Control": "no-store"}


def _enforce_limit(request: Request, key: str) -> None:
    limiter = request.app.state.rate_limiter
    if not limiter:
        return
    wait = limiter.retry_after(key)
    if wait > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Try again later.",
            headers=_retry_header(wait),
        )


@router.post("/register", response_model=AuthOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Annotated[Database, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthOut:
    _enforce_limit(request, f"register:{_client_ip(request)}")
    problems = check_password(payload.email, payload.password)
    if problems:
        raise HTTPException(status_code=422, detail=problems[0])

    existing = await db.row("SELECT id FROM users WHERE email = ?", (payload.email,))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )

    user_id = new_id()
    await db.execute(
        "INSERT INTO users (id, email, password_hash, created_at_utc) VALUES (?, ?, ?, ?)",
        (user_id, payload.email, hash_password(payload.password), now_utc()),
    )
    await seed_catalog(db, user_id)
    token, expires_at = await create_session(db, user_id, settings)
    set_session_cookies(response, settings, token, expires_at)
    return AuthOut(
        user=UserOut(
            id=user_id,
            email=payload.email,
            created_at_utc=await _created_at(db, user_id),
        )
    )


async def _created_at(db: Database, user_id: str) -> int:
    value = await db.value("SELECT created_at_utc FROM users WHERE id = ?", (user_id,))
    return int(value) if value is not None else now_utc()


@router.post("/login", response_model=AuthOut)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Database, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthOut:
    ip = _client_ip(request)
    _enforce_limit(request, f"login-ip:{ip}")
    _enforce_limit(request, f"login-email:{payload.email}")

    row = await db.row(
        "SELECT id, password_hash, created_at_utc FROM users WHERE email = ?",
        (payload.email,),
    )
    limiter = request.app.state.rate_limiter
    # Same message and the same Argon2 cost whether or not the account exists.
    stored_hash = row["password_hash"] if row is not None else _DUMMY_HASH
    if not verify_password(stored_hash, payload.password) or row is None:
        if limiter:
            limiter.record_failure(f"login-ip:{ip}")
            limiter.record_failure(f"login-email:{payload.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
            headers=_retry_header(0),
        )

    if limiter:
        limiter.record_success(f"login-ip:{ip}")
        limiter.record_success(f"login-email:{payload.email}")

    if password_needs_rehash(row["password_hash"]):
        await db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(payload.password), row["id"]),
        )

    token, expires_at = await create_session(db, row["id"], settings)
    set_session_cookies(response, settings, token, expires_at)
    return AuthOut(
        user=UserOut(id=row["id"], email=payload.email, created_at_utc=int(row["created_at_utc"]))
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: Annotated[Database, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    token = request.cookies.get(settings.session_cookie)
    await revoke_session(db, token)
    clear_session_cookies(response, settings)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    request: Request,
    response: Response,
    db: Annotated[Database, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    token = request.cookies.get(settings.session_cookie)
    user_id = await db.value(
        "SELECT user_id FROM sessions WHERE token_hash = ?", (token_digest(token or ""),)
    )
    if user_id is not None:
        await revoke_all_sessions(db, str(user_id))
    clear_session_cookies(response, settings)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=AuthOut)
async def me(user: AuthedUser) -> AuthOut:
    return AuthOut(user=UserOut(**user))
