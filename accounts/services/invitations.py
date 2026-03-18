from __future__ import annotations

import json
from email.utils import formataddr
from typing import Any
from urllib import error, request

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.template.loader import render_to_string
from django.urls import reverse

from accounts.models import Invitation

POSTMARK_API_URL = "https://api.postmarkapp.com/email"


class PostmarkEmailError(RuntimeError):
    """Raised when Postmark rejects or fails to accept an email request."""


token = getattr(settings, "POSTMARK_SERVER_TOKEN", None)
if not token:
    raise ImproperlyConfigured("Missing required setting: POSTMARK_SERVER_TOKEN")


def _get_setting(name: str, default: Any = None) -> Any:
    return getattr(settings, name, default)


def _required_setting(name: str) -> Any:
    value = _get_setting(name)
    if value in (None, ""):
        raise ImproperlyConfigured(f"Missing required setting: {name}")
    return value


def _clean_subject(value: str) -> str:
    return " ".join((value or "").splitlines()).strip()


def _build_invite_url(invitation: Invitation, request_obj=None) -> str:
    path = reverse("accounts:invite_start", args=[invitation.token])
    if request_obj is not None:
        return request_obj.build_absolute_uri(path)

    site_url = (_get_setting("SITE_URL", "") or "").strip().rstrip("/")
    if not site_url:
        raise ImproperlyConfigured(
            "SITE_URL is required when sending invitation email without an HTTP request."
        )
    return f"{site_url}{path}"


def send_invitation_email(*, invitation: Invitation, request_obj=None) -> None:
    """Send an invitation email using the Postmark API only."""
    server_token = _required_setting("POSTMARK_SERVER_TOKEN")
    from_email = _required_setting("DEFAULT_FROM_EMAIL")
    reply_to = (_get_setting("REPLY_TO_EMAIL", "") or "").strip()
    app_name = (_get_setting("APP_NAME", "MoneyPro") or "MoneyPro").strip()
    invite_url = _build_invite_url(invitation, request_obj=request_obj)

    context = {
        "invitation": invitation,
        "invite_url": invite_url,
        "app_name": app_name,
        "expires_at": invitation.expires_at,
        "reply_to_email": reply_to,
        "support_email": reply_to or from_email,
    }

    subject = _clean_subject(
        render_to_string("accounts/emails/invitation_subject.txt", context)
    )
    text_body = render_to_string("accounts/emails/invitation_email.txt", context)
    html_body = render_to_string("accounts/emails/invitation_email.html", context)

    payload = {
        "From": formataddr((app_name, from_email)),
        "To": invitation.email,
        "Subject": subject,
        "TextBody": text_body,
        "HtmlBody": html_body,
        "MessageStream": (_get_setting("POSTMARK_MESSAGE_STREAM", "outbound") or "outbound"),
    }
    if reply_to:
        payload["ReplyTo"] = reply_to

    req = request.Request(
        POSTMARK_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": server_token,
        },
    )

    try:
        with request.urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8")
            data = json.loads(body) if body else {}
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            details = json.loads(raw)
            message = details.get("Message") or raw
        except json.JSONDecodeError:
            message = raw or str(exc)
        raise PostmarkEmailError(f"Postmark API error {exc.code}: {message}") from exc
    except error.URLError as exc:
        raise PostmarkEmailError(f"Could not connect to Postmark: {exc}") from exc

    if data.get("ErrorCode"):
        raise PostmarkEmailError(
            f"Postmark rejected email: {data.get('Message', 'Unknown error')}"
        )
