# core/middleware.py
from __future__ import annotations

from django.shortcuts import redirect
from django.urls import reverse

from core.models import BusinessMembership


class ActiveBusinessMiddleware:
    """
    Enforce "single active business" for authenticated users.

    Rules:
    - If the user is authenticated and DOES NOT have an active BusinessMembership,
      redirect them to accounts onboarding (which will create the business + membership).
    - Never block admin or auth/account flows to prevent redirect loops.
    - Expose the active business on request.business for downstream views/templates.

    Notes:
    - This middleware assumes accounts.OnboardingView is the *only* onboarding step
      and is responsible for creating Business + BusinessMembership.
    """

    # URL prefixes that must never be blocked (avoid loops)
    ALLOW_PREFIXES = (
        "/admin/",
        "/accounts/",
        "/static/",
        "/media/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Default for templates/views; always set.
        request.business = None

        # Anonymous users can proceed normally.
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Allowlisted paths: do not enforce business requirement here.
        # This avoids loops for login/signup/reset + admin + static/media.
        path = request.path or "/"
        if any(path.startswith(prefix) for prefix in self.ALLOW_PREFIXES):
            return self.get_response(request)

        # Resolve active membership (single active business per user).
        membership = (
            BusinessMembership.objects.filter(user=request.user, is_active=True)
            .select_related("business")
            .first()
        )

        if not membership:
            # Redirect to the single onboarding flow (CompanyProfile + Business creation).
            # Use reverse so it stays correct if you change urls later.
            onboarding_url = reverse("accounts:onboarding")

            # Preserve where they were going; onboarding can ignore or use this.
            return redirect(f"{onboarding_url}?next={request.get_full_path()}")

        # Attach active business for downstream use.
        request.business = membership.business
        return self.get_response(request)
