from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy, reverse
from django.views.generic import UpdateView
from django.views import View

from .forms import CompanyProfileForm, UserInfoForm
from .models import CompanyProfile


from ledger.services import seed_schedule_c_defaults




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
        if self.object.is_complete:
            seed_schedule_c_defaults(self.request.user)
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
            company_form = CompanyProfileForm(request.POST, instance=profile, prefix="company")
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
