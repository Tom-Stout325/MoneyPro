from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from project.views import home

def healthcheck(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", healthcheck, name="healthcheck"),
    path("", home, name="home"),

    path("accounts/", include("accounts.urls")),
    path("accounts/", include("allauth.urls")),


    path("dashboard/", include("dashboard.urls")),
    path("business/", include("core.urls", namespace="core")),
    path("", include("ledger.urls")),
    path("reports/", include("reports.urls", namespace="reports")),
    path("vehicles/", include("vehicles.urls", namespace="vehicles")),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
