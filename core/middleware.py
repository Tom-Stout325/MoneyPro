# core/middleware.py
from __future__ import annotations

from django.shortcuts import redirect
from django.urls import reverse

from core.models import BusinessMembership, UserBusinessState


class ActiveBusinessMiddleware:
    """
    Attaches request.business for authenticated users.

    If missing, redirect to business onboarding. This middleware is intentionally
    strict so every request has a tenant context once we start switching models.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.business = None

        # Always allow unauthenticated users through.
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Allow auth/admin and business setup routes to avoid loops.
        allowed_prefixes = ("/accounts/", "/admin/", "/business/", "/static/", "/media/")
        if request.path.startswith(allowed_prefixes):
            return self.get_response(request)

        state, _ = UserBusinessState.objects.get_or_create(user=request.user)
        biz = state.active_business

        if biz and BusinessMembership.objects.filter(user=request.user, business=biz, is_active=True).exists():
            request.business = biz
            return self.get_response(request)

        # If user has at least one membership, auto-select the first
        membership = (
            BusinessMembership.objects.filter(user=request.user, is_active=True)
            .select_related("business")
            .order_by("business__name")
            .first()
        )
        if membership:
            state.active_business = membership.business
            state.save(update_fields=["active_business"])
            request.business = membership.business
            return self.get_response(request)

        # No business yet -> route user to onboarding
        onboarding_url = reverse("core:business_onboarding")
        if request.path != onboarding_url:
            return redirect("core:business_onboarding")

        return self.get_response(request)
