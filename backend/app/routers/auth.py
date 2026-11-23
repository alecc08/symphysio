"""Auth endpoints: register, login, logout, session check, email confirmation.

Rate limited per IP (and per account on login) to blunt password spraying.
Email confirmation is optional: with no Resend key configured the app stays
fully usable and every account is treated as verified.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from ..db import Database
from ..deps import AuthedUser, get_db, get_settings
from ..emails import confirmation_message
from ..ids import new_id, now_utc
from ..mailer import Mailer, Message
from ..password_policy import check_password
from ..schemas import AuthOut, LoginRequest, RegisterRequest, UserOut, VerifyRequest
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
from ..verification import (
    CONFIRM_EMAIL,
    VerifyOutcome,
    consume_verification,
    count_recent_sends,
    create_verification,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    """Best-effort client address (trust X-Forwarded-For only behind your proxy)."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_mailer(request: Request) -> Mailer:
    mailer: Mailer = request.app.state.mailer
    return mailer


MailerDep = Annotated[Mailer, Depends(get_mailer)]


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


async def _issue_confirmation(
    db: Database, settings: Settings, mailer: Mailer, user_id: str, email: str
) -> tuple[str, int] | None:
    """Create and mail a confirmation link. Returns (token, expiry) or None if capped.

    The send itself is queued as a background task by the caller: the response must
    not depend on Resend being reachable.
    """
    if not settings.email_enabled:
        return None
    recent = await count_recent_sends(db, user_id, 3600)
    if recent >= settings.email_sends_per_hour:
        return None
    token = await create_verification(
        db, user_id, CONFIRM_EMAIL, settings.email_verification_ttl_seconds
    )
    return token, now_utc() + settings.email_verification_ttl_seconds


async def _deliver(mailer: Mailer, message: Message) -> None:
    """Background task: never raises, never logs a token or a full address."""
    await mailer.send(message)


@router.post("/register", response_model=AuthOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    background: BackgroundTasks,
    db: Annotated[Database, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    mailer: MailerDep,
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

    # Without email there is nothing to confirm, so the account is simply verified;
    # a LAN deployment with no outbound mail stays fully usable.
    verified = 0 if settings.email_enabled else 1
    user_id = new_id()
    await db.execute(
        "INSERT INTO users (id, email, password_hash, created_at_utc, is_verified)"
        " VALUES (?, ?, ?, ?, ?)",
        (user_id, payload.email, hash_password(payload.password), now_utc(), verified),
    )
    await seed_catalog(db, user_id)

    issued = await _issue_confirmation(db, settings, mailer, user_id, payload.email)
    if issued is not None:
        token, _ = issued
        background.add_task(_deliver, mailer, confirmation_message(settings, payload.email, token))

    # In hard mode a new account cannot use its session until the link is clicked.
    if settings.require_email_verification and settings.email_enabled:
        return AuthOut(
            user=UserOut(
                id=user_id,
                email=payload.email,
                created_at_utc=await _created_at(db, user_id),
                is_verified=False,
            )
        )

    token, expires_at = await create_session(db, user_id, settings)
    set_session_cookies(response, settings, token, expires_at)
    return AuthOut(
        user=UserOut(
            id=user_id,
            email=payload.email,
            created_at_utc=await _created_at(db, user_id),
            is_verified=bool(verified),
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
    background: BackgroundTasks,
    db: Annotated[Database, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    mailer: MailerDep,
) -> AuthOut:
    ip = _client_ip(request)
    _enforce_limit(request, f"login-ip:{ip}")
    _enforce_limit(request, f"login-email:{payload.email}")

    row = await db.row(
        "SELECT id, password_hash, created_at_utc, is_verified FROM users WHERE email = ?",
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

    if settings.require_email_verification and not bool(row["is_verified"]):
        # Hard mode is opt-in. Send a fresh link so the person is never stuck on
        # a 403 with no way forward, subject to the same per-hour cap.
        issued = await _issue_confirmation(db, settings, mailer, str(row["id"]), payload.email)
        if issued is not None:
            token, _ = issued
            background.add_task(
                _deliver, mailer, confirmation_message(settings, payload.email, token)
            )
        # An HTTPException would drop the queued send, so answer with a response
        # that carries the background task.
        denial = JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Confirm your email first — we have just sent you a new link."},
        )
        denial.background = background
        return denial

    token, expires_at = await create_session(db, row["id"], settings)
    set_session_cookies(response, settings, token, expires_at)
    return AuthOut(
        user=UserOut(
            id=row["id"],
            email=payload.email,
            created_at_utc=int(row["created_at_utc"]),
            is_verified=bool(row["is_verified"]),
        )
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


@router.post("/verify", status_code=status.HTTP_204_NO_CONTENT)
async def verify(
    payload: VerifyRequest,
    request: Request,
    db: Annotated[Database, Depends(get_db)],
) -> Response:
    """Consume a confirmation token. The token arrives in the JSON body, never in a
    URL the server logs, so the SPA reads it from ``?token=`` and posts it here."""
    ip = _client_ip(request)
    _enforce_limit(request, f"verify:{ip}")
    limiter = request.app.state.rate_limiter

    outcome = await consume_verification(db, payload.token, CONFIRM_EMAIL)
    if outcome == VerifyOutcome.OK:
        if limiter:
            limiter.record_success(f"verify:{ip}")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # A wrong token matches no row, so guessing is bounded by this counter rather
    # than by anything stored per token.
    if limiter:
        limiter.record_failure(f"verify:{ip}")
    if outcome == VerifyOutcome.EXPIRED:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="That confirmation link has expired. Request a new one.",
        )
    if outcome == VerifyOutcome.USED:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="That confirmation link has already been used.",
        )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="That confirmation link is not valid.",
    )


@router.post("/verify/resend", status_code=status.HTTP_202_ACCEPTED)
async def verify_resend(
    request: Request,
    background: BackgroundTasks,
    user: AuthedUser,
    db: Annotated[Database, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    mailer: MailerDep,
) -> Response:
    """Re-send the confirmation link. The previous link stops working."""
    if not settings.email_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email confirmation is not configured on this server.",
        )
    if user.get("is_verified"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account is already confirmed.",
        )
    _enforce_limit(request, f"resend:{_client_ip(request)}")
    issued = await _issue_confirmation(db, settings, mailer, str(user["id"]), str(user["email"]))
    if issued is None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Only {settings.email_sends_per_hour} emails per hour are sent.",
            headers=_retry_header(3600),
        )
    token, _ = issued
    background.add_task(_deliver, mailer, confirmation_message(settings, str(user["email"]), token))
    return Response(status_code=status.HTTP_202_ACCEPTED)
