from django.urls import path
from .views import OnboardingView, SettingsView

app_name = "accounts"

urlpatterns = [
    path("onboarding/", OnboardingView.as_view(), name="onboarding"),
    path("settings/", SettingsView.as_view(), name="settings"),
]
