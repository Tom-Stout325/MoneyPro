from django.urls import path

from .views import dashboard_home, seed_defaults

app_name = "dashboard"

urlpatterns = [
    path("", dashboard_home, name="home"),
    path("seed-defaults/", seed_defaults, name="seed_defaults"),
]
