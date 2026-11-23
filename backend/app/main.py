"""FastAPI application factory: security headers, hard limits, SPA static serving.

Zero dynamic execution anywhere: the API only accepts and returns JSON, and the
frontend is a compiled bundle served as static files.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .db import Database
from .mailer import build_mailer
from .ratelimit import RateLimiter
from .routers import analytics, auth, catalog, export, logs
from .security import csrf_matches, new_csrf_token
from .settings import Settings, get_settings
from .verification import prune_verifications

logger = logging.getLogger("symphysio")

API_PREFIX = "/api/v1"

# The version has exactly one home: the repo-root VERSION file. The image copies
# that file next to the app, so the running app, the git tag and the image label
# cannot disagree, and a test enforces it from the source checkout.
_VERSION_CANDIDATES = (
    Path(__file__).resolve().parent.parent / "VERSION",  # /app/VERSION in the image
    Path(__file__).resolve().parent.parent.parent / "VERSION",  # repo root, running from backend/
)


def read_version() -> str:
    for path in _VERSION_CANDIDATES:
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
    return "0.0.0+local"


__version__ = read_version()

# No inline scripts, no third-party origins, no framing, no plugin content.
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:;"
    " font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self';"
    " form-action 'self'; frame-ancestors 'none'; frame-src 'none'; upgrade-insecure-requests"
)
SECURITY_HEADERS: dict[str, str] = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-DNS-Prefetch-Control": "off",
    "Cache-Control": "no-store",
}

# State-changing methods need the double-submit CSRF header when a session exists.
CSRF_EXEMPT_PATHS = frozenset({f"{API_PREFIX}/auth/login", f"{API_PREFIX}/auth/register"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = getattr(app.state, "settings", None) or get_settings()
    db = Database(settings)
    await db.connect()
    app.state.settings = settings
    app.state.db = db
    app.state.rate_limiter = (
        RateLimiter(
            attempts=settings.rate_limit_attempts,
            window_seconds=settings.rate_limit_window_seconds,
            lockout_seconds=settings.rate_limit_lockout_seconds,
        )
        if settings.rate_limit_enabled
        else None
    )
    pruned = await db.prune_sessions()
    if pruned:
        logger.info("pruned %d expired session(s)", pruned)
    pruned_tokens = await prune_verifications(db)
    if pruned_tokens:
        logger.info("pruned %d spent or expired verification token(s)", pruned_tokens)
    app.state.mailer = build_mailer(settings)
    if settings.require_email_verification and not settings.email_enabled:
        # A gate nobody can pass is a bug, not a policy: refuse the combination.
        raise RuntimeError(
            "SYPHYSIO_EMAIL_CONFIRMATION=required but no mail transport is configured; "
            "set RESEND_API_KEY, SYPHYSIO_EMAIL_FROM and SYPHYSIO_PUBLIC_URL, or use "
            "SYPHYSIO_EMAIL_CONFIRMATION=optional (or off)."
        )
    logger.info(
        "symphysio ready (db=%s, email=%s, confirmation=%s%s)",
        settings.database_path,
        settings.mail_backend,
        settings.email_confirmation,
        "" if not settings.email_enabled else f", from={settings.email_from}",
    )
    try:
        yield
    finally:
        await db.close()


def _needs_csrf_check(request: Request, settings: Settings) -> bool:
    """State-changing API call that rides on a session cookie must prove CSRF."""
    return (
        request.method not in SAFE_METHODS
        and request.url.path.startswith(API_PREFIX)
        and request.url.path not in CSRF_EXEMPT_PATHS
        and bool(request.cookies.get(settings.session_cookie))
    )


def _should_issue_csrf(request: Request, settings: Settings) -> bool:
    return (
        request.method in SAFE_METHODS
        and request.url.path.startswith(API_PREFIX)
        and bool(request.cookies.get(settings.session_cookie))
        and not request.cookies.get(settings.csrf_cookie)
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        title="Symphysio API",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    if settings is not None:  # tests inject their own settings before lifespan runs
        app.state.settings = settings

    @app.middleware("http")
    async def csrf_guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        app_settings: Settings = getattr(app.state, "settings", get_settings())
        if _needs_csrf_check(request, app_settings) and not csrf_matches(
            request.headers.get("x-csrf-token"),
            request.cookies.get(app_settings.csrf_cookie),
        ):
            # Double-submit: the header must match the readable CSRF cookie.
            return JSONResponse(
                {"detail": "CSRF token missing or invalid."},
                status_code=status.HTTP_403_FORBIDDEN,
            )
        response = await call_next(request)
        # Bootstrap: a live session whose CSRF cookie was cleared gets a fresh one.
        if _should_issue_csrf(request, app_settings):
            response.set_cookie(
                key=app_settings.csrf_cookie,
                value=new_csrf_token(),
                max_age=app_settings.session_ttl_seconds,
                path="/",
                httponly=False,
                secure=app_settings.cookie_secure,
                samesite="lax",
            )
        return response

    @app.middleware("http")
    async def limit_body(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        limit: int = getattr(app.state, "settings", get_settings()).max_body_bytes
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > limit:
            return JSONResponse({"detail": "Request body too large"}, status_code=413)
        return await call_next(request)

    @app.middleware("http")
    async def harden(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        for key, value in SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        return response

    for module in (auth, catalog, logs, analytics, export):
        app.include_router(module.router, prefix=API_PREFIX)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    def spa_index() -> Path | None:
        app_settings = getattr(app.state, "settings", get_settings())
        index_html = Path(app_settings.static_dir) / "index.html"
        return index_html if index_html.is_file() else None

    @app.get("/", include_in_schema=False)
    async def index() -> Response:
        index_html = spa_index()
        if index_html is None:
            return JSONResponse(
                {
                    "app": "symphysio",
                    "version": __version__,
                    "message": "API is running. Build the frontend (npm run build) "
                    "or set SYPHYSIO_STATIC_DIR to the compiled bundle.",
                    "openapi": f"{API_PREFIX}/openapi.json",
                }
            )
        return FileResponse(index_html, media_type="text/html")

    # The confirmation link in the email points here; the SPA reads ?token= and
    # posts it to /api/v1/auth/verify, then rewrites the URL.
    @app.get("/verify", include_in_schema=False)
    async def verify_shell() -> Response:
        index_html = spa_index()
        if index_html is None:
            return JSONResponse(
                {"detail": "Build the frontend to use the confirmation page."},
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return FileResponse(index_html, media_type="text/html")

    app_settings = getattr(app.state, "settings", get_settings())
    static_dir = Path(app_settings.static_dir)
    if (static_dir / "assets").is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="spa")

    return app


app = create_app()
