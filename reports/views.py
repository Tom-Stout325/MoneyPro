# reports/views.py
from __future__ import annotations

from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from ledger.reporting_utils import (
    route_category_for_report,
    route_subcategory_for_report,
)
from .queries import aggregate_category_subcategory_totals


class ReportsHomeView(LoginRequiredMixin, TemplateView):
    template_name = "reports/home.html"


class ScheduleCSummaryView(LoginRequiredMixin, TemplateView):
    template_name = "reports/schedule_c_summary.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        today = date.today()

        # Filters
        mode = (self.request.GET.get("mode") or "tax").lower()
        if mode not in ("book", "tax"):
            mode = "tax"

        try:
            year = int(self.request.GET.get("year") or today.year)
        except ValueError:
            year = today.year

        date_from = date(year, 1, 1)
        date_to = today if year == today.year else date(year, 12, 31)

        # Data
        categories = aggregate_category_subcategory_totals(
            user=self.request.user,
            date_from=date_from,
            date_to=date_to,
            mode=mode,
        )

        # Group into Parts (Part I, Part II, Part V)
        parts: dict[str, list] = {"Part I": [], "Part II": [], "Part III": [], "Part IV": [], "Part V": []}

        for cat in categories:
            cat_group = route_category_for_report(
                category_name=cat.category_name,
                schedule_c_line=cat.schedule_c_line,
                report_group=cat.report_group,
            )

            # For subcategory rows, route to Part V if it's "Other Expenses (27b)" breakdown
            # (We keep cat total in Part II; the breakdown list appears in Part V)
            sub_group = route_subcategory_for_report(
                category_name=cat.category_name,
                schedule_c_line=cat.schedule_c_line,
                default_group=cat.report_group,
            )

            if cat_group == "Part II" and sub_group == "Part V":
                parts["Part II"].append({**cat.__dict__, "subcategories": [], "detail_only": False})
                parts["Part V"].append({**cat.__dict__, "detail_only": True})
            else:
                parts.setdefault(cat_group, []).append({**cat.__dict__, "detail_only": False})

        # Totals per part
        def part_total(items):
            return sum((i["total"] for i in items), 0)

        parts_display = {
            name: {
                "items": items,
                "total": part_total(items),
            }
            for name, items in parts.items()
        }

        ctx.update(
            {
                "mode": mode,
                "year": year,
                "year_options": list(range(2023, today.year + 1)),
                "date_from": date_from,
                "date_to": date_to,
                "parts": parts_display,
                "grand_total": sum((c.total for c in categories), 0),
            }
        )


        return ctx
