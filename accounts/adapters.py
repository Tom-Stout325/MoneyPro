from __future__ import annotations

from django.utils import timezone
from allauth.account.adapter import DefaultAccountAdapter

from core.models import Business, BusinessMembership
from .models import Invitation


class InviteOnlyAccountAdapter(DefaultAccountAdapter):
    """Invite-only signup adapter.

    Normal public signup is disabled.
    Signup is allowed only when a valid Invitation token has been placed into
    the session (via `accounts.views.invite_start`).
    """

    SESSION_INVITE_TOKEN_KEY = "invite_token"
    SESSION_INVITE_EMAIL_KEY = "invite_email"

    def _get_invitation_from_session(self, request):
        if request is None:
            return None

        token = (request.session.get(self.SESSION_INVITE_TOKEN_KEY) or "").strip()
        if not token:
            token = (request.GET.get("invite") or "").strip()
        if not token:
            return None

        try:
            inv = Invitation.objects.get(token=token)
        except Invitation.DoesNotExist:
            return None

        if inv.is_expired or inv.is_used:
            return None

        request.session[self.SESSION_INVITE_TOKEN_KEY] = inv.token
        request.session[self.SESSION_INVITE_EMAIL_KEY] = (inv.email or "").strip().lower()
        request.session.modified = True

        return inv

    def is_open_for_signup(self, request):
        """Gate signup: only allow when the session contains a valid invite."""
        return self._get_invitation_from_session(request) is not None

    def save_user(self, request, user, form, commit=True):
        """On successful signup, mark the invite as accepted."""
        user = super().save_user(request, user, form, commit=commit)

        if commit:
            # Create a default business if user doesn't already have one
            if not BusinessMembership.objects.filter(user=user, is_active=True).exists():
                biz = Business.objects.create(
                    name=(user.get_full_name() or user.username or "My Business")
                )
                BusinessMembership.objects.create(
                    user=user,
                    business=biz,
                    role=BusinessMembership.Role.OWNER,
                    is_active=True,
                )

        inv = self._get_invitation_from_session(request)
        if inv is not None:
            invited_email = (inv.email or "").strip().lower()
            if invited_email:
                user.email = invited_email

            if commit:
                user.save(update_fields=["email"])

            inv.accepted_user = user
            inv.accepted_at = timezone.now()
            inv.save(update_fields=["accepted_user", "accepted_at"])

            try:
                request.session.pop(self.SESSION_INVITE_TOKEN_KEY, None)
                request.session.pop(self.SESSION_INVITE_EMAIL_KEY, None)
                request.session[self.SESSION_INVITE_TOKEN_KEY] = inv.token
                request.session[self.SESSION_INVITE_EMAIL_KEY] = inv.email.lower()
                request.session.modified = True
            except Exception:
                pass

        return user
