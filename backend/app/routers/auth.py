"""Auth endpoints: register, login, logout, session check, email confirmation.

Rate limited per IP (and per account on login) to blunt password spraying.
Email confirmation is optional: with no Resend key configured the app stays
fully usable and every account is treated as verified.
"""

from __future__ import annotations

import secrets
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from ..clientip import client_ip
from ..db import Database
from ..deps import AuthedUser, get_db, get_settings
from ..emails import confirmation_message, password_reset_message
from ..i18n import DEFAULT_LOCALE, from_headers, normalize, t
from ..ids import new_id, now_utc
from ..mailer import Mailer, Message
from ..password_policy import check_password
from ..schemas import (
    AuthOut,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    PreferencesOut,
    PreferencesUpdate,
    RegisterRequest,
    UserOut,
    VerifyRequest,
)
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
from ..timezones import effective, utc_offset_label
from ..verification import (
    CONFIRM_EMAIL,
    PASSWORD_RESET,
    VerifyOutcome,
    consume_verification,
    count_recent_sends,
    create_verification,
    verification_owner,
)

router = APIRouter(prefix="/auth", tags=["auth"])


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
            detail=t("err.too_many_attempts", from_headers(request.headers)),
            headers=_retry_header(wait),
        )


def _record_failure(request: Request, key: str) -> None:
    """Charge the limiter for an attempt that did not create an account.

    The limiter only counts what it is told about: without this the `register:`
    window is never filled and the check above can never trip, which would leave
    account creation — the one endpoint that pays for an Argon2 hash — unmetered.
    """
    limiter = request.app.state.rate_limiter
    if limiter:
        limiter.record_failure(key)


async def _issue_confirmation(
    db: Database, settings: Settings, mailer: Mailer, user_id: str, email: str
) -> tuple[str, int] | None:
    """Create and mail a confirmation link. Returns (token, expiry) or None if capped.

    The send itself is queued as a background task by the caller: the response must
    not depend on Resend being reachable.
    """
    if not settings.confirmation_enabled:
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
    ip = client_ip(request)
    _enforce_limit(request, f"register:{ip}")
    if not settings.allow_registration:
        # Charged to the limiter like any other rejected attempt: a closed door
        # should cost a scanner the same budget as an open one.
        _record_failure(request, f"register:{ip}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t("err.registration_closed", from_headers(request.headers)),
        )
    # The body's choice wins; without one, the request's `Accept-Language` answers.
    # `negotiate`, not `normalize`: this is a header list with quality values, and a
    # browser that says `fr-CA,fr;q=0.9,en;q=0.8` is not saying the literal string.
    locale = payload.locale or from_headers(request.headers)
    problems = check_password(payload.email, payload.password, locale)
    if problems:
        _record_failure(request, f"register:{ip}")
        raise HTTPException(status_code=422, detail=problems[0])

    existing = await db.row("SELECT id FROM users WHERE email = ?", (payload.email,))
    if existing is not None:
        _record_failure(request, f"register:{ip}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=t("err.email_taken", locale),
        )

    # Nothing to confirm when the admin turned email off or no transport is
    # configured, so the account is simply verified and a LAN-only deployment
    # stays fully usable.
    verified = 0 if settings.confirmation_enabled else 1
    user_id = new_id()
    await db.execute(
        "INSERT INTO users (id, email, password_hash, created_at_utc, is_verified, profile_key,"
        " locale, timezone)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user_id,
            payload.email,
            hash_password(payload.password),
            now_utc(),
            verified,
            payload.profile,
            locale,
            # Only an explicit choice is stored. A zone inferred from this one
            # request (or from the instance default) is not something to pin to
            # the account forever: NULL means "never chose", which is what keeps
            # the instance default meaningful.
            payload.timezone or None,
        ),
    )
    # Seeded in the account's language, because these become rows: a preset name
    # is data the person can rename, not chrome the app can re-translate later.
    await seed_catalog(db, user_id, payload.profile, locale)

    issued = await _issue_confirmation(db, settings, mailer, user_id, payload.email)
    if issued is not None:
        token, _ = issued
        background.add_task(
            _deliver, mailer, confirmation_message(settings, payload.email, token, locale)
        )

    stored = await _user_row(db, user_id)

    # In hard mode a new account cannot use its session until the link is clicked.
    if settings.require_email_verification and settings.confirmation_enabled:
        return AuthOut(user=UserOut(**{**stored, "is_verified": False}))

    token, expires_at = await create_session(db, user_id, settings)
    set_session_cookies(response, settings, token, expires_at)
    return AuthOut(user=UserOut(**{**stored, "is_verified": bool(verified)}))


async def _user_row(db: Database, user_id: str) -> dict[str, object]:
    """The account's own public fields, for the responses that build a `UserOut`."""
    row = await db.row(
        "SELECT id, email, created_at_utc, is_verified, profile_key, locale, timezone"
        " FROM users WHERE id = ?",
        (user_id,),
    )
    if row is None:  # we just wrote the row
        return {"id": user_id, "email": "", "created_at_utc": now_utc(), "is_verified": True}
    row["is_verified"] = bool(row["is_verified"])
    return row


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
    ip = client_ip(request)
    _enforce_limit(request, f"login-ip:{ip}")
    _enforce_limit(request, f"login-email:{payload.email}")

    row = await db.row(
        "SELECT id, password_hash, created_at_utc, is_verified, profile_key, locale, timezone"
        " FROM users WHERE email = ?",
        (payload.email,),
    )
    limiter = request.app.state.rate_limiter
    # Same message and the same Argon2 cost whether or not the account exists.
    stored_hash = row["password_hash"] if row is not None else _DUMMY_HASH
    if not verify_password(stored_hash, payload.password) or row is None:
        if limiter:
            limiter.record_failure(f"login-ip:{ip}")
            limiter.record_failure(f"login-email:{payload.email}")
        # Deliberately the *request's* language, never the stored preference:
        # answering this one in French only for accounts that happen to be French
        # would turn a failed login into an oracle for "does this address exist".
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("err.bad_credentials", from_headers(request.headers)),
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

    # From here the password matched, so the account's own language is safe to
    # use: it is no longer an answer an attacker can probe for.
    account_locale = normalize(row["locale"])

    if settings.require_email_verification and not bool(row["is_verified"]):
        # Hard mode is opt-in. Send a fresh link so the person is never stuck on
        # a 403 with no way forward, subject to the same per-hour cap.
        issued = await _issue_confirmation(db, settings, mailer, str(row["id"]), payload.email)
        if issued is not None:
            token, _ = issued
            background.add_task(
                _deliver,
                mailer,
                confirmation_message(settings, payload.email, token, account_locale),
            )
        # An HTTPException would drop the queued send, so answer with a response
        # that carries the background task.
        denial = JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": t("err.confirm_first", account_locale)},
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
            profile_key=str(row["profile_key"]),
            locale=account_locale,
            timezone=row["timezone"],
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


# -- preferences ---------------------------------------------------------
#
# Two account-level settings that change what the *server* says and how it cuts
# a day. They live on the account, not in the browser, for one reason each: the
# language decides the wording of an email that is read away from this browser,
# and the zone decides what "today" means for an insights card computed on the
# server. Both are read by the same session lookup that already runs per request.


def _preferences(request: Request, user: dict[str, Any], settings: Settings) -> PreferencesOut:
    zone = effective(
        user.get("timezone"), request.headers.get("x-timezone"), settings.default_timezone
    )
    return PreferencesOut(
        locale=normalize(user.get("locale")),
        timezone=user.get("timezone"),
        effective_timezone=zone,
        utc_offset=utc_offset_label(zone),
    )


@router.get("/preferences", response_model=PreferencesOut)
async def get_preferences(
    request: Request,
    user: AuthedUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> PreferencesOut:
    """What the account holds, plus what the server is actually using.

    The distinction matters: an account that never chose a zone displays the
    instance default, and Settings has to say so rather than show a blank.
    """
    return _preferences(request, user, settings)


@router.patch("/preferences", response_model=PreferencesOut)
async def patch_preferences(
    payload: PreferencesUpdate,
    request: Request,
    user: AuthedUser,
    db: Annotated[Database, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PreferencesOut:
    """Language and time zone. Neither rewrites anything already logged.

    A zone sent as `null` or `""` is cleared, which puts the account back under
    the instance default — the honest way to undo a wrong pick. The account's
    language changes the app, the API's error text and future emails; the preset
    names it was seeded with are rows now, and stay as they were written.
    """
    changed = payload.model_dump(exclude_unset=True)
    if not changed:
        raise HTTPException(
            status_code=422, detail=t("err.nothing_to_change", from_headers(request.headers))
        )
    locale = changed.get("locale") or str(user.get("locale") or DEFAULT_LOCALE)
    # `null` and `""` both mean "clear it", which puts the account back under the
    # instance default rather than pinning it to a wrong guess forever.
    timezone = (changed["timezone"] or None) if "timezone" in changed else user.get("timezone")
    await db.execute(
        "UPDATE users SET locale = ?, timezone = ? WHERE id = ?",
        (normalize(locale), timezone, str(user["id"])),
    )
    updated = {**user, "locale": normalize(locale), "timezone": timezone}
    return _preferences(request, updated, settings)


@router.post("/verify", status_code=status.HTTP_204_NO_CONTENT)
async def verify(
    payload: VerifyRequest,
    request: Request,
    db: Annotated[Database, Depends(get_db)],
) -> Response:
    """Consume a confirmation token. The token arrives in the JSON body, never in a
    URL the server logs: the mail's link carries it as a URL fragment (``#token=``),
    which the browser never sends here, and the SPA posts it to this endpoint."""
    ip = client_ip(request)
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
            detail=t("err.verify_expired", from_headers(request.headers)),
        )
    if outcome == VerifyOutcome.USED:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=t("err.verify_used", from_headers(request.headers)),
        )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=t("err.verify_invalid", from_headers(request.headers)),
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
    locale = from_headers(request.headers, user)
    if not settings.confirmation_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=t("err.verify_disabled", locale),
        )
    if user.get("is_verified"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=t("err.already_verified", locale),
        )
    _enforce_limit(request, f"resend:{client_ip(request)}")
    issued = await _issue_confirmation(db, settings, mailer, str(user["id"]), str(user["email"]))
    if issued is None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=t("err.send_cap", locale, limit=settings.email_sends_per_hour),
            headers=_retry_header(3600),
        )
    token, _ = issued
    background.add_task(
        _deliver, mailer, confirmation_message(settings, str(user["email"]), token, locale)
    )
    return Response(status_code=status.HTTP_202_ACCEPTED)


# -- password reset --------------------------------------------------------
#
# Same token discipline as confirmation: 256-bit random, stored only as a
# SHA-256 digest, single use, short TTL — see app/verification.py. What differs
# is the blast radius: a confirmation link can only ever confirm an address,
# while a reset link hands over the account. So the TTL is 30 minutes rather than
# 24 hours, and using it revokes every session.


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
async def password_reset_request(
    payload: PasswordResetRequest,
    request: Request,
    background: BackgroundTasks,
    db: Annotated[Database, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    mailer: MailerDep,
) -> Response:
    """Mail a reset link. The answer is identical whether or not the address exists.

    Enumeration is the whole attack surface here: this endpoint is public, so it
    must not vary by account. Unknown address, known address, and known address
    over the send budget all answer `202 Accepted` with the same body (empty).
    """
    ip = client_ip(request)
    _enforce_limit(request, f"pwreset-ip:{ip}")
    _enforce_limit(request, f"pwreset-email:{payload.email}")
    request_locale = from_headers(request.headers)
    if not settings.email_enabled:
        # A deployment fact, not an account fact: without a mail transport nobody
        # can recover anything, and saying so is kinder than a silent 202.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=t("err.no_mail_transport", request_locale),
        )

    row = await db.row("SELECT id, locale FROM users WHERE email = ?", (payload.email,))
    if row is None:
        # Charged to the IP budget: a spray of unknown addresses has to cost
        # something, and a typo costs the sender one attempt out of a generous IP
        # window rather than locking the account's real owner out.
        _record_failure(request, f"pwreset-ip:{ip}")
        return Response(status_code=status.HTTP_202_ACCEPTED, headers=_retry_header(0))

    recent = await count_recent_sends(db, str(row["id"]), 3600, PASSWORD_RESET)
    if recent >= settings.email_sends_per_hour:
        return Response(status_code=status.HTTP_202_ACCEPTED, headers=_retry_header(3600))

    token = await create_verification(
        db, str(row["id"]), PASSWORD_RESET, settings.password_reset_ttl_seconds
    )
    # The *mail* follows the account's language — that address already belongs to
    # the person, and the response above stayed byte-identical either way.
    background.add_task(
        _deliver,
        mailer,
        password_reset_message(settings, payload.email, token, normalize(row["locale"])),
    )
    return Response(status_code=status.HTTP_202_ACCEPTED, headers=_retry_header(0))


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def password_reset_confirm(
    payload: PasswordResetConfirm,
    request: Request,
    response: Response,
    db: Annotated[Database, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Use a reset link: set the password, then sign every session out.

    Order matters twice over. The password is validated *before* the token is
    consumed, so a rejected password does not burn a single-use link; and the
    response for a weak password is the same whether the token was real or not,
    so this endpoint cannot be used to fish for live tokens.
    """
    ip = client_ip(request)
    _enforce_limit(request, f"pwreset-confirm:{ip}")
    limiter = request.app.state.rate_limiter
    # Every answer here is in the *request's* language, never the account's. The
    # docstring's invariant is that a weak password reads the same whether the
    # token was real or not; answering in the owner's French only for a live
    # token would break it and turn wording into a token probe.
    request_locale = from_headers(request.headers)

    owner = await verification_owner(db, payload.token, PASSWORD_RESET)
    email = ""
    if owner is not None:
        row = await db.row("SELECT email FROM users WHERE id = ?", (owner,))
        email = str(row["email"]) if row else ""
    problems = check_password(email, payload.password, request_locale)
    if problems:
        if limiter:
            limiter.record_failure(f"pwreset-confirm:{ip}")
        raise HTTPException(status_code=422, detail=problems[0])

    outcome = await consume_verification(db, payload.token, PASSWORD_RESET)
    if outcome != VerifyOutcome.OK:
        if limiter:
            limiter.record_failure(f"pwreset-confirm:{ip}")
        if outcome == VerifyOutcome.EXPIRED:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail=t("err.reset_expired", request_locale),
            )
        if outcome == VerifyOutcome.USED:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail=t("err.reset_used", request_locale),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("err.reset_invalid", request_locale),
        )

    if owner is None:  # consume_verification returned OK, so this is unreachable
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=t("err.reset_failed", request_locale),
        ) from None
    await db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (hash_password(payload.password), owner),
    )
    # The point of the whole flow: whoever held the old password, on any device,
    # is out. Sessions are rows, so revoking is a delete, and a stolen cookie that
    # is still sitting in some other browser stops working on its next request.
    revoked = await revoke_all_sessions(db, owner)
    clear_session_cookies(response, settings)
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers={"X-Revoked-Sessions": str(revoked), **_retry_header(0)},
    )
