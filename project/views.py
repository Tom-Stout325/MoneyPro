# project/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from core.models import BusinessMembership



def home(request):
    if request.user.is_authenticated:
        profile = getattr(request.user, "company_profile", None)
        has_membership = BusinessMembership.objects.filter(user=request.user, is_active=True).exists()

        if not profile or not profile.is_complete or not has_membership:
            return redirect("accounts:onboarding")

        return redirect("dashboard:home")

    return render(request, "home.html")
