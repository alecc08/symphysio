"""Email copy.

Hard rules, because this inbox sits next to a person's health diary:

* no symptom names, no counts, no dates from the log — not even a friendly
  "you have 3 entries this week";
* no images and no tracking pixel (an image request would leak the open to a
  third party);
* plain text plus a minimal HTML part, escaped, built by hand — no templating.
"""

from __future__ import annotations

from html import escape

from .mailer import Message
from .settings import Settings

SUBJECT = "Confirm your Symphysio account"


def verification_link(settings: Settings, token: str) -> str:
    """Absolute link. Host comes from config, never from the request's Host header."""
    if settings.public_url is None:  # guarded by Settings.email_enabled
        raise RuntimeError("SYPHYSIO_PUBLIC_URL is required to build a verification link")
    return f"{settings.public_url}/verify?token={token}"


def confirmation_message(settings: Settings, to: str, token: str) -> Message:
    link = verification_link(settings, token)
    hours = max(1, settings.email_verification_ttl_seconds // 3600)
    text = (
        "Confirm your Symphysio account\n\n"
        "Open this link to confirm the address you signed up with. It works for\n"
        f"{hours} hour{'s' if hours != 1 else ''} and can only be used once.\n\n"
        f"{link}\n\n"
        "You can keep using Symphysio while it is unconfirmed. Confirming only\n"
        "means you can recover the account if you lose your phone.\n\n"
        "If you did not create this account, ignore this email — nothing has been\n"
        "confirmed, and it will expire on its own.\n\n"
        "Symphysio never sends health information by email.\n"
    )
    safe_link = escape(link, quote=True)
    html = (
        "<!doctype html><html><body style=\"margin:0;padding:24px;"
        "font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#0f172a;"
        "background:#f8fafc\">"
        '<div style="max-width:440px;margin:0 auto;padding:24px;background:#fff;'
        'border:1px solid #e2e8f0;border-radius:16px">'
        '<p style="margin:0 0 12px;font-size:17px;font-weight:700">Confirm your email</p>'
        "<p style=\"margin:0 0 16px;font-size:15px;line-height:1.5\">Open this link to confirm"
        f" the address you signed up with. It works for {hours} hour"
        f"{'s' if hours != 1 else ''} and can only be used once.</p>"
        '<p style="margin:0 0 20px"><a href="' + safe_link + '" style="display:inline-block;'
        'padding:12px 18px;background:#0d9488;color:#ffffff;text-decoration:none;'
        'border-radius:12px;font-weight:700">Confirm account</a></p>'
        '<p style="margin:0 0 16px;font-size:13px;word-break:break-all;color:#475569">'
        '<a href="' + safe_link + '" style="color:#475569">' + safe_link + "</a></p>"
        '<p style="margin:0;font-size:13px;line-height:1.5;color:#64748b">You can keep using'
        " Symphysio while this is unconfirmed. Confirming only means you can recover the"
        " account later. If you did not create this account, ignore this email. Symphysio"
        " never sends health information by email.</p>"
        "</div></body></html>"
    )
    return Message(to=to, subject=SUBJECT, text=text, html=html)


__all__ = ["SUBJECT", "confirmation_message", "verification_link"]
