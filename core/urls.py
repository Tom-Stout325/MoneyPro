from django.urls import path

from core import views

app_name = "core"

urlpatterns = [
    path("onboarding/", views.business_onboarding, name="business_onboarding"),
    path("switch/", views.business_switch, name="business_switch"),
]
