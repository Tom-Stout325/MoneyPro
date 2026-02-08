# reports/urls.py
from django.urls import path
from . import views

app_name = "reports"

urlpatterns = [
    path("", views.ReportsHomeView.as_view(), name="home"),
    path("schedule-c-summary/", views.ScheduleCSummaryView.as_view(), name="schedule_c_summary"),
]
