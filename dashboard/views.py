from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render




@login_required
def dashboard_home(request):
    profile = getattr(request.user, "company_profile", None)
    if not profile or not profile.is_complete:
        return redirect("accounts:onboarding")
    return render(request, "dashboard/home.html")


