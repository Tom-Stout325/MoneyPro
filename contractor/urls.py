from __future__ import annotations

from django.urls import path

from . import views

app_name = "contractor"

urlpatterns = [
    path("", views.ContractorListView.as_view(), name="list"),
    path("<int:pk>/", views.ContractorDetailView.as_view(), name="detail"),
    path("<int:pk>/w9/requested/", views.mark_w9_requested, name="mark_w9_requested"),
    path("<int:pk>/w9/send/", views.send_w9_email, name="send_w9_email"),
    path("<int:pk>/w9/view/", views.w9_view, name="w9_view"),

    # Public portal (no login)
    path("w9/<str:token>/", views.w9_portal, name="w9_portal"),

    # 1099-NEC (keep a backwards-compatible alias name to avoid template drift)
    path("1099/", views.nec_1099_center, name="1099_center"),
    path("1099/", views.nec_1099_center, name="1099_home"),  # alias
    path("1099/<int:pk>/", views.nec_1099_preview, name="1099_preview"),
    path("1099/<int:pk>/pdf/", views.nec_1099_pdf, name="1099_pdf"),

    path("1099/<int:pk>/store/", views.store_1099_pdf, name="1099_store"),
    path("1099/<int:pk>/email/", views.email_1099_copy_b, name="1099_email_copy_b"),
]
