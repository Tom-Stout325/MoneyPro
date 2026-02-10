from __future__ import annotations

from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from vehicles.models import Vehicle
from vehicles.queries import get_yearly_mileage_summary


class YearlyMileageReportView(LoginRequiredMixin, TemplateView):
    template_name = "vehicles/reports/yearly_mileage_report.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        today = date.today()
        try:
            year = int(self.request.GET.get("year") or today.year)
        except ValueError:
            year = today.year

        vehicles = Vehicle.objects.filter(business=self.request.business, is_active=True).order_by("sort_order", "label")

        summaries = []
        for v in vehicles:
            try:
                summary = get_yearly_mileage_summary(business=self.request.business, vehicle_id=v.id, year=year)
            except Exception:
                continue
            summaries.append(summary)

        ctx.update(
            {
                "year": year,
                "year_options": list(range(2023, today.year + 1)),
                "vehicles": vehicles,
                "summaries": summaries,
            }
        )
        return ctx
