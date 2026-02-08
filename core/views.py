from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.models import CompanyProfile
from core.forms import BusinessCreateForm, BusinessSwitchForm
from core.models import BusinessMembership, UserBusinessState


@login_required
def business_onboarding(request: HttpRequest) -> HttpResponse:
    """Create the first business for a user who has none."""
    # If user already has a business, send them to switch page.
    if BusinessMembership.objects.filter(user=request.user, is_active=True).exists():
        return redirect("core:business_switch")

    initial = {}
    try:
        profile = CompanyProfile.objects.get(user=request.user)
        if profile.company_name:
            initial["name"] = profile.company_name
    except CompanyProfile.DoesNotExist:
        pass

    if request.method == "POST":
        form = BusinessCreateForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                biz = form.save()
                BusinessMembership.objects.create(
                    business=biz,
                    user=request.user,
                    role=BusinessMembership.Role.OWNER,
                )
                state, _ = UserBusinessState.objects.get_or_create(user=request.user)
                state.active_business = biz
                state.save(update_fields=["active_business"])
            messages.success(request, "Business created.")
            return redirect("dashboard:home")
    else:
        form = BusinessCreateForm(initial=initial)

    return render(request, "core/business_onboarding.html", {"form": form})


@login_required
def business_switch(request: HttpRequest) -> HttpResponse:
    """Choose the active business when the user belongs to multiple businesses."""
    memberships = BusinessMembership.objects.filter(user=request.user, is_active=True)
    if not memberships.exists():
        return redirect("core:business_onboarding")

    if memberships.count() == 1:
        # Auto-set the only business and continue.
        membership = memberships.select_related("business").first()
        state, _ = UserBusinessState.objects.get_or_create(user=request.user)
        state.active_business = membership.business
        state.save(update_fields=["active_business"])
        return redirect("dashboard:home")

    if request.method == "POST":
        form = BusinessSwitchForm(request.POST, user=request.user)
        if form.is_valid():
            biz_id = int(form.cleaned_data["business_id"])
            membership = memberships.filter(business_id=biz_id).select_related("business").first()
            if membership:
                state, _ = UserBusinessState.objects.get_or_create(user=request.user)
                state.active_business = membership.business
                state.save(update_fields=["active_business"])
                messages.success(request, f"Switched to {membership.business.name}.")
                return redirect("dashboard:home")
            messages.error(request, "Invalid business selection.")
    else:
        form = BusinessSwitchForm(user=request.user)
        # Preselect active business if present
        state, _ = UserBusinessState.objects.get_or_create(user=request.user)
        if state.active_business_id:
            form.initial = {"business_id": state.active_business_id}

    return render(request, "core/business_switch.html", {"form": form})
