# project/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

def home(request):
    if request.user.is_authenticated:
        profile = getattr(request.user, "company_profile", None)
        if not profile or not profile.is_complete:
            return redirect("accounts:onboarding")
        return redirect("dashboard:home")
    return render(request, "home.html")
