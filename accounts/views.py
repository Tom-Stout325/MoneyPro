from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import logout
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse_lazy, reverse
from django.views import View
from django.views.generic import UpdateView
from django.db import transaction

from .forms import CompanyProfileForm, UserInfoForm
from .models import CompanyProfile, Invitation
from .adapters import InviteOnlyAccountAdapter
from core.models import Business, BusinessMembership



class OnboardingView(LoginRequiredMixin, UpdateView):
    model = CompanyProfile
    form_class = CompanyProfileForm
    template_name = "accounts/onboarding.html"
    success_url = reverse_lazy("dashboard:home")

    def get_object(self, queryset=None):
        profile, created = CompanyProfile.objects.get_or_create(user=self.request.user)
        if created and not profile.company_name:
            profile.company_name = getattr(settings, "DEFAULT_COMPANY_NAME", "")
            profile.save(update_fields=["company_name"])
        return profile

    def dispatch(self, request, *args, **kwargs):
        profile, _ = CompanyProfile.objects.get_or_create(user=request.user)
        if profile.is_complete and request.method.lower() == "get":
            return redirect("dashboard:home")
        return super().dispatch(request, *args, **kwargs)

def form_valid(self, form):
    response = super().form_valid(form)

    # once profile is complete, create business/membership if missing
    if self.object.is_complete:
        with transaction.atomic():
            membership = (
                BusinessMembership.objects.select_for_update()
                .filter(user=self.request.user, is_active=True)
                .select_related("business")
                .first()
            )
            if not membership:
                biz = Business.objects.create(name=self.object.company_name or "My Business")
                BusinessMembership.objects.create(
                    business=biz,
                    user=self.request.user,
                    role=BusinessMembership.Role.OWNER,
                    is_active=True,
                )

        # force fresh login AFTER the single onboarding flow
        logout(self.request)
        messages.success(self.request, "Account setup complete. Please log in again to continue.")
        return redirect("account_login")

    return response

    

class SettingsView(LoginRequiredMixin, View):
    template_name = "accounts/settings.html"

    def _get_profile(self, request):
        profile, _ = CompanyProfile.objects.get_or_create(user=request.user)
        return profile

    def dispatch(self, request, *args, **kwargs):
        profile = self._get_profile(request)
        if not profile.is_complete:
            return redirect("accounts:onboarding")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        profile = self._get_profile(request)
        return render(
            request,
            self.template_name,
            {
                "company_form": CompanyProfileForm(instance=profile, prefix="company"),
                "user_form": UserInfoForm(instance=request.user, prefix="user"),
            },
        )

    def post(self, request):
        profile = self._get_profile(request)
        form_id = request.POST.get("form_id", "")

        company_form = CompanyProfileForm(instance=profile, prefix="company")
        user_form = UserInfoForm(instance=request.user, prefix="user")

        if form_id == "company":
            company_form = CompanyProfileForm(request.POST, request.FILES, instance=profile, prefix="company")
            if company_form.is_valid():
                company_form.save()
                messages.success(request, "Company settings saved.")
                return redirect("accounts:settings")

        elif form_id == "user":
            user_form = UserInfoForm(request.POST, instance=request.user, prefix="user")
            if user_form.is_valid():
                user_form.save()
                messages.success(request, "User info updated.")
                return redirect("accounts:settings")

        else:
            messages.error(request, "Invalid form submission.")

        return render(
            request,
            self.template_name,
            {"company_form": company_form, "user_form": user_form},
        )


def invite_start(request, token: str):
    """Validate an invitation token and redirect the user to allauth signup.

    This stores the invitation token + email into session so the allauth
    adapter can allow signup and lock the email address.
    """

    try:
        inv = Invitation.objects.select_related("invited_by").get(token=token)
    except Invitation.DoesNotExist:
        raise Http404("Invalid invitation link.")

    if inv.is_expired:
        raise Http404("Invitation expired.")

    if inv.is_used:
        raise Http404("Invitation already used.")

    adapter = InviteOnlyAccountAdapter()
    request.session[adapter.SESSION_INVITE_TOKEN_KEY] = inv.token
    request.session[adapter.SESSION_INVITE_EMAIL_KEY] = (inv.email or "").strip().lower()

    messages.info(request, "Your invite has been validated. Create your account to continue.")
    return redirect("account_signup")
