from __future__ import annotations

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from core.emailing import business_from_email, formatted_from_header, normalize_reply_to, uses_preview_backend


def send_w9_request_email(*, business, contractor_name: str, contractor_email: str, portal_url: str, owner_user=None) -> tuple[bool, str]:
    from_name, from_email, reply_to = business_from_email(business=business, owner_user=owner_user)

    context = {
        "business_name": business.name,
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
        from_email=formatted_from_header(display_name=from_name, email=from_email),
        to=[contractor_email],
        reply_to=normalize_reply_to(reply_to),
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)

    if uses_preview_backend():
        return False, "Email preview generated using the current placeholder/local email backend."
    return True, "W-9 request email sent."
