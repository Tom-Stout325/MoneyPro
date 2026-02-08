from __future__ import annotations

from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from vehicles.models import Vehicle, VehicleYear
from vehicles.queries import get_yearly_mileage_summary


class YearlyMileageReportView(LoginRequiredMixin, TemplateView):
    template_name = "vehicles/yearly_mileage_report.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        today = date.today()
        try:
            year = int(self.request.GET.get("year") or today.year)
        except ValueError:
            year = today.year

        # Vehicles to choose from (only active business vehicles)
        vehicles_qs = Vehicle.objects.filter(
            user=self.request.user,
            is_active=True,
            is_business=True,
        ).order_by("sort_order", "label")

        # If vehicle not selected, try to pick the first vehicle that has a VehicleYear row for this year.
        vehicle_id_raw = (self.request.GET.get("vehicle") or "").strip()
        vehicle_id = int(vehicle_id_raw) if vehicle_id_raw.isdigit() else None
        if vehicle_id is None:
            vy = (
                VehicleYear.objects.filter(
                    user=self.request.user,
                    year=year,
                    vehicle__is_active=True,
                    vehicle__is_business=True,
                )
                .select_related("vehicle")
                .order_by("vehicle__sort_order", "vehicle__label")
                .first()
            )
            if vy:
                vehicle_id = vy.vehicle_id



        summary = None
        missing_setup = False

        if vehicle_id:
            try:
                summary = get_yearly_mileage_summary(user=self.request.user, vehicle_id=vehicle_id, year=year)
            except VehicleYear.DoesNotExist:
                missing_setup = True

        ctx.update(
            {
                "year": year,
                "year_options": list(range(2023, today.year + 1)),
                "vehicles": vehicles_qs,
                "vehicle_id": vehicle_id,
                "summary": summary,
                "missing_setup": missing_setup,
            }
        )
        return ctx
