from __future__ import annotations

from email.utils import formataddr

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def _setting(name: str, default: str = "") -> str:
    return str(getattr(settings, name, default) or default)


def _uses_preview_backend() -> bool:
    backend = _setting("EMAIL_BACKEND").strip().lower()
    return backend in {
        "django.core.mail.backends.console.emailbackend",
        "django.core.mail.backends.filebased.emailbackend",
        "django.core.mail.backends.locmem.emailbackend",
        "django.core.mail.backends.dummy.emailbackend",
    }


def send_w9_request_email(*, business_name: str, contractor_name: str, contractor_email: str, portal_url: str) -> tuple[bool, str]:
    from_email = _setting("DEFAULT_FROM_EMAIL", "no-reply@example.test")
    reply_to = _setting("REPLY_TO_EMAIL", from_email)
    app_name = _setting("APP_NAME", "MoneyPro")

    context = {
        "business_name": business_name,
        "contractor_name": contractor_name,
        "portal_url": portal_url,
        "support_email": reply_to or from_email,
    }
    subject = render_to_string("contractor/emails/w9_request_subject.txt", context).strip().replace("\n", " ")
    text_body = render_to_string("contractor/emails/w9_request_email.txt", context)
    html_body = render_to_string("contractor/emails/w9_request_email.html", context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=formataddr((app_name, from_email)),
        to=[contractor_email],
        reply_to=[reply_to] if reply_to else None,
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)

    if _uses_preview_backend():
        return False, "Email preview generated using the current placeholder/local email backend."
    return True, "W-9 request email sent."
