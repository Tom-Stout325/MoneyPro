from __future__ import annotations
from django.urls import path
from . import views

app_name = "reports"

urlpatterns = [
    path("", views.ReportsHomeView.as_view(), name="home"),
    path("schedule-c/", views.schedule_c, name="schedule_c"),
    path("schedule-c/yoy/", views.schedule_c_yoy, name="schedule_c_yoy"),
    path("schedule-c/pdf/preview/", views.schedule_c_pdf_preview, name="schedule_c_pdf_preview"),
    path("schedule-c/pdf/download/", views.schedule_c_pdf_download, name="schedule_c_pdf_download"),
    path("schedule-c/yoy/pdf/preview/", views.schedule_c_yoy_pdf_preview, name="schedule_c_yoy_pdf_preview"),
    path("schedule-c/yoy/pdf/download/", views.schedule_c_yoy_pdf_download, name="schedule_c_yoy_pdf_download"),

    # Profit & Loss (Books)
    path("profit-loss/", views.profit_loss, name="profit_loss"),
    path("profit-loss/yoy/", views.profit_loss_yoy, name="profit_loss_yoy"),
    path("profit-loss/pdf/preview/", views.profit_loss_pdf_preview, name="profit_loss_pdf_preview"),
    path("profit-loss/pdf/download/", views.profit_loss_pdf_download, name="profit_loss_pdf_download"),
    path("profit-loss/yoy/pdf/preview/", views.profit_loss_yoy_pdf_preview, name="profit_loss_yoy_pdf_preview"),
    path("profit-loss/yoy/pdf/download/", views.profit_loss_yoy_pdf_download, name="profit_loss_yoy_pdf_download"),
]
