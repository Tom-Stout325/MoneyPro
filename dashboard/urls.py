from django.urls import path

from .views import dashboard_chart_data, dashboard_home, seed_defaults

app_name = "dashboard"

urlpatterns = [
    path("", dashboard_home, name="home"),
    path("chart-data/", dashboard_chart_data, name="chart_data"),
    path("seed-defaults/", seed_defaults, name="seed_defaults"),
]
