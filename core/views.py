# core/views.py
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render

from core.models import Business, BusinessMembership
from core.forms import BusinessOnboardingForm


@login_required
def business_onboarding(request):
    """
    Create the (single) business for this user.

    Rule: user may have at most one ACTIVE membership.
    If already active, go to dashboard.
    """

    if BusinessMembership.objects.filter(user=request.user, is_active=True).exists():
        return redirect("dashboard:home")

    if request.method == "POST":
        form = BusinessOnboardingForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Re-check inside transaction (double-submit protection)
                if BusinessMembership.objects.select_for_update().filter(
                    user=request.user, is_active=True
                ).exists():
                    return redirect("dashboard:home")

                business: Business = form.save()

                BusinessMembership.objects.create(
                    business=business,
                    user=request.user,
                    role=BusinessMembership.Role.OWNER,
                    is_active=True,
                )

            # Force a fresh login after business creation
            logout(request)
            messages.success(request, "Business created. Please log in again to continue.")
            return redirect("account_login")
    else:
        form = BusinessOnboardingForm()

    return render(request, "core/business_onboarding.html", {"form": form})
