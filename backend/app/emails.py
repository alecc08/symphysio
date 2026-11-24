"""Email copy, in the account's language.

Hard rules, because this inbox sits next to a person's health diary:

* no symptom names, no counts, no dates from the log — not even a friendly
  "you have 3 entries this week";
* no images and no tracking pixel (an image request would leak the open to a
  third party);
* plain text plus a minimal HTML part, escaped, built by hand — no templating.

Both parts are assembled from the same ``mail.*`` strings in ``app/messages.py``,
so the plain-text mail and its HTML twin cannot drift apart, and a French account
gets a French mail. The language comes from the account
(``users.locale``) — for a password reset that is already in hand, because the
flow looks the account up by address; for sign-up it comes from the request.
"""

from __future__ import annotations

from html import escape

from .i18n import DEFAULT_LOCALE, t
from .mailer import Message
from .settings import Settings


def verification_link(settings: Settings, token: str) -> str:
    """Absolute link. Host comes from config, never from the request's Host header."""
    if settings.public_url is None:  # guarded by Settings.email_enabled
        raise RuntimeError("SYMPHYSIO_PUBLIC_URL is required to build a verification link")
    # A fragment, not a query string: the browser never sends the part after `#`
    # to the server, so no access log — Traefik's, uvicorn's, or a CDN's — can
    # ever record a live confirmation token. A `?token=` link did get logged:
    # measured, uvicorn recorded `GET /verify?token=…` when the link was opened.
    return f"{settings.public_url}/verify#token={token}"


def _unit(locale: str, count: int, kind: str) -> str:
    """`hour`/`hours`, `minute`/`minutes`, in the language being written."""
    return t(f"mail.{kind}_one" if count == 1 else f"mail.{kind}_many", locale)


def _html(
    settings: Settings,
    *,
    heading: str,
    lead: str,
    button: str,
    link: str,
    note: str,
) -> str:
    """The minimal HTML part. Same escape discipline and same copy as the text."""
    safe_link = escape(link, quote=True)
    return (
        '<!doctype html><html><body style="margin:0;padding:24px;'
        'font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#0f172a;'
        'background:#f8fafc">'
        '<div style="max-width:440px;margin:0 auto;padding:24px;background:#fff;'
        'border:1px solid #e2e8f0;border-radius:16px">'
        f'<p style="margin:0 0 12px;font-size:17px;font-weight:700">{escape(heading)}</p>'
        f'<p style="margin:0 0 16px;font-size:15px;line-height:1.5">{escape(lead)}</p>'
        '<p style="margin:0 0 20px"><a href="' + safe_link + '" style="display:inline-block;'
        'padding:12px 18px;background:#0d9488;color:#ffffff;text-decoration:none;'
        'border-radius:12px;font-weight:700">' + escape(button) + "</a></p>"
        '<p style="margin:0 0 16px;font-size:13px;word-break:break-all;color:#475569">'
        '<a href="' + safe_link + '" style="color:#475569">' + safe_link + "</a></p>"
        '<p style="margin:0;font-size:13px;line-height:1.5;color:#64748b">' + escape(note) + "</p>"
        "</div></body></html>"
    )


def confirmation_message(
    settings: Settings, to: str, token: str, locale: str = DEFAULT_LOCALE
) -> Message:
    """The confirm-your-address mail. Says nothing about what the account holds."""
    link = verification_link(settings, token)
    hours = max(1, settings.email_verification_ttl_seconds // 3600)
    subject = t("mail.verify_subject", locale)
    lead = t("mail.verify_open", locale, count=hours, unit=_unit(locale, hours, "hour"))
    harmless = t("mail.verify_harmless", locale)
    not_you = t("mail.verify_not_you", locale)
    never_health = t("mail.never_health", locale)
    text = (
        f"{subject}\n\n"
        f"{lead}\n\n"
        f"{link}\n\n"
        f"{harmless}\n\n"
        f"{not_you}\n\n"
        f"{never_health}\n"
    )
    return Message(
        to=to,
        subject=subject,
        text=text,
        html=_html(
            settings,
            heading=t("mail.verify_heading", locale),
            lead=lead,
            button=t("mail.verify_button", locale),
            link=link,
            note=f"{harmless} {not_you} {never_health}",
        ),
    )


def reset_link(settings: Settings, token: str) -> str:
    """Same fragment discipline as the confirmation link: no access log sees it."""
    if settings.public_url is None:  # guarded by Settings.email_enabled
        raise RuntimeError("SYMPHYSIO_PUBLIC_URL is required to build a password reset link")
    return f"{settings.public_url}/reset#token={token}"


def password_reset_message(
    settings: Settings, to: str, token: str, locale: str = DEFAULT_LOCALE
) -> Message:
    """The reset mail. Deliberately says nothing about what the account contains."""
    link = reset_link(settings, token)
    minutes = max(1, settings.password_reset_ttl_seconds // 60)
    subject = t("mail.reset_subject", locale)
    lead = t("mail.reset_open", locale, count=minutes, unit=_unit(locale, minutes, "minute"))
    signout = t("mail.reset_signout", locale)
    not_you = t("mail.reset_not_you", locale)
    never_health = t("mail.never_health", locale)
    text = (
        f"{subject}\n\n"
        f"{lead}\n\n"
        f"{link}\n\n"
        f"{signout}\n\n"
        f"{not_you}\n\n"
        f"{never_health}\n"
    )
    return Message(
        to=to,
        subject=subject,
        text=text,
        html=_html(
            settings,
            heading=t("mail.reset_heading", locale),
            lead=lead,
            button=t("mail.reset_button", locale),
            link=link,
            note=f"{signout} {not_you} {never_health}",
        ),
    )


__all__ = [
    "confirmation_message",
    "password_reset_message",
    "reset_link",
    "verification_link",
]
