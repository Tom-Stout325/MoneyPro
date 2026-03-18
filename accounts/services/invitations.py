from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags

from accounts.models import Invitation


def build_invitation_url(request, invitation: Invitation) -> str:
    return request.build_absolute_uri(
        reverse("accounts:invite_start", args=[invitation.token])
    )


def send_invitation_email(request, invitation: Invitation) -> None:
    invite_url = build_invitation_url(request, invitation)
    business_name = ""
    context = {
        "invitation": invitation,
        "invite_url": invite_url,
        "site_name": getattr(settings, "INVITE_SITE_NAME", "MoneyPro"),
        "support_email": getattr(settings, "DEFAULT_FROM_EMAIL", "webmaster@localhost"),
        "business_name": business_name,
    }

    subject = render_to_string("accounts/emails/invitation_subject.txt", context).strip().replace("\n", " ")
    text_body = render_to_string("accounts/emails/invitation_email.txt", context)
    html_body = render_to_string("accounts/emails/invitation_email.html", context)

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "webmaster@localhost"

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=from_email,
        to=[invitation.email],
    )
    message.attach_alternative(html_body, "text/html")
    # Fallback plain body if a client strips MIME alternative weirdly.
    if not text_body.strip():
        message.body = strip_tags(html_body)
    message.send(fail_silently=False)
