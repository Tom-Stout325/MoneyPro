# core/middleware.py
from __future__ import annotations

from django.shortcuts import redirect
from django.urls import reverse

from core.models import BusinessMembership


class ActiveBusinessMiddleware:

    ALLOW_PREFIXES = (
        "/admin/",
        "/accounts/",
        "/static/",
        "/media/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        request.business = None

        if not request.user.is_authenticated:
            return self.get_response(request)

        path = request.path or "/"
        if any(path.startswith(prefix) for prefix in self.ALLOW_PREFIXES):
            return self.get_response(request)

        membership = (
            BusinessMembership.objects.filter(user=request.user, is_active=True)
            .select_related("business")
            .first()
        )

        if not membership:
            onboarding_url = reverse("accounts:onboarding")
            return redirect(f"{onboarding_url}?next={request.get_full_path()}")

        request.business = membership.business
        return self.get_response(request)
