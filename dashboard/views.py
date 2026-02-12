from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from core.models import BusinessMembership
from ledger.models import Category





@login_required
def dashboard_home(request):
    profile = getattr(request.user, "company_profile", None)  # ok if OneToOne
    has_membership = BusinessMembership.objects.filter(user=request.user, is_active=True).exists()

    if not profile or not profile.is_complete or not has_membership:
        return redirect("accounts:onboarding")

    categories_seeded = bool(
        getattr(request, "business", None)
        and Category.objects.filter(business=request.business).exists()
    )

    return render(
        request,
        "dashboard/home.html",
        {
            "categories_seeded": categories_seeded,
        },
    )


@login_required
def seed_defaults(request):
    """Seed (or re-seed) default Categories/SubCategories for the active business."""

    if request.method != "POST":
        return redirect("dashboard:home")

    business = getattr(request, "business", None)
    if business is None:
        return redirect("accounts:onboarding")

    membership = (
        BusinessMembership.objects.filter(user=request.user, business=business, is_active=True)
        .only("role")
        .first()
    )
    if not membership or membership.role not in (
        BusinessMembership.Role.OWNER,
        BusinessMembership.Role.ADMIN,
    ):
        messages.error(request, "You don't have permission to seed defaults for this business.")
        return redirect("dashboard:home")

    from ledger.services import seed_schedule_c_defaults

    already_seeded = Category.objects.filter(business=business).exists()
    seed_schedule_c_defaults(business)

    messages.success(
        request,
        "Defaults re-seeded." if already_seeded else "Defaults seeded.",
    )
    return redirect("dashboard:home")